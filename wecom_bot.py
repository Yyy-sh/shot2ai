"""企业微信智能机器人长连接客户端（基于 websocket-client 同步实现）。

协议要点（wss://openws.work.weixin.qq.com）：
  - 连接后发 aibot_subscribe {bot_id, secret} 鉴权
  - 每 30 秒发 ping 心跳
  - 收到 aibot_msg_callback 为用户消息，body 含 chatid/chattype/from.userid/msgtype
  - 主动发送 aibot_send_msg {chatid, chat_type, msgtype, ...}（需用户先发过消息）
  - 图片：先 aibot_upload_media_init/chunk(≤512KB)/finish 拿 media_id，再发 image 消息
  - 响应帧用 headers.req_id 关联请求（不依赖 cmd 命名）
"""
import base64
import hashlib
import json
import threading
import time
import uuid

import websocket  # pip install websocket-client


class WeComBot:
    def __init__(self, bot_id: str, secret: str, ws_url: str = "wss://openws.work.weixin.qq.com"):
        self.bot_id = bot_id
        self.secret = secret
        self.ws_url = ws_url
        self.ws = None
        self._send_lock = threading.Lock()
        self._stop = False
        self._responses = {}            # req_id -> {"event": Event, "result": None, "cmd": cmd}
        self._resp_lock = threading.Lock()
        self._callbacks = {}            # msgtype -> callable(body)
        self._user_chat = None          # (target, chat_type, userid)
        self._chat_event = threading.Event()
        self._thread = None
        self._debug = True              # 调试日志开关

    # ---------- 底层发送 / req_id 关联 ----------
    @staticmethod
    def _gen_req_id() -> str:
        return uuid.uuid4().hex

    def _send_frame(self, cmd: str, body: dict, req_id: str = None) -> str:
        req_id = req_id or self._gen_req_id()
        frame = {"cmd": cmd, "headers": {"req_id": req_id}, "body": body}
        data = json.dumps(frame, ensure_ascii=False)
        if self._debug:
            print(f"[企微 debug→] 发送 cmd={cmd} req_id={req_id[:8]}")
        with self._send_lock:
            if self.ws is None:
                raise RuntimeError("WebSocket 未连接")
            self.ws.send(data)
        return req_id

    def _request(self, cmd: str, body: dict, timeout: float = 30) -> dict:
        """发送指令并等待响应帧，返回 body。

        用 req_id 关联响应（不依赖响应帧的 cmd 命名）。
        """
        req_id = self._gen_req_id()
        event = threading.Event()
        with self._resp_lock:
            self._responses[req_id] = {"event": event, "result": None, "cmd": cmd}
        try:
            self._send_frame(cmd, body, req_id)
            if not event.wait(timeout):
                if self._debug:
                    print(f"[企微 debug] ⏰ 等待 {cmd} 响应超时({timeout}s)")
                return {}
            with self._resp_lock:
                entry = self._responses.get(req_id, {})
                return entry.get("result") or {}
        finally:
            with self._resp_lock:
                self._responses.pop(req_id, None)

    # ---------- 连接 / 生命周期 ----------
    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()

    def _run_forever(self):
        backoff = 1
        while not self._stop:
            try:
                self.ws.run_forever(ping_interval=0)  # 自管心跳
                backoff = 1
            except Exception as e:
                print(f"[企微] run_forever 异常: {e}")
            if self._stop:
                break
            print(f"[企微] 连接断开，{backoff}s 后重连 ...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def stop(self):
        self._stop = True
        if self.ws:
            self.ws.close()

    # ---------- WebSocket 回调 ----------
    def _on_open(self, ws):
        print("[企微] WebSocket 已连接，正在认证 ...")
        self._send_frame("aibot_subscribe", {"bot_id": self.bot_id, "secret": self.secret})
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def _heartbeat(self):
        while not self._stop:
            time.sleep(30)
            try:
                self._send_frame("ping", {})
            except Exception:
                break

    def _on_message(self, ws, message):
        try:
            frame = json.loads(message)
        except Exception:
            return
        cmd = frame.get("cmd", "")
        headers = frame.get("headers", {})
        body = frame.get("body", {})
        req_id = headers.get("req_id", "")

        if self._debug:
            print(f"[企微 debug←] 收到 cmd={cmd} req_id={req_id[:8]}")

        # 用 req_id 直接关联响应（不依赖 cmd 命名）
        if req_id:
            with self._resp_lock:
                entry = self._responses.get(req_id)
                if entry is not None:
                    entry["result"] = body
                    entry["event"].set()
                    # 认证响应特殊提示
                    if entry.get("cmd") == "aibot_subscribe":
                        errcode = body.get("errcode", -1)
                        print(f"[企微] 认证{'成功' if errcode == 0 else '失败'}: {body}")
                    return

        # 消息回调
        if cmd == "aibot_msg_callback":
            self._handle_message(body)
            return

        # 事件回调
        if cmd == "aibot_event_callback":
            print(f"[企微] 事件: {body.get('event_type')}")
            return

    def _on_error(self, ws, error):
        print(f"[企微] 错误: {error}")

    def _on_close(self, ws, code, msg):
        print(f"[企微] 连接关闭: code={code} {msg}")

    # ---------- 收消息 ----------
    def _handle_message(self, body):
        msgtype = body.get("msgtype", "")
        userid = body.get("from", {}).get("userid", "")
        chatid = body.get("chatid", "")
        chattype = body.get("chattype", "single")
        chat_type = 1 if chattype == "single" else 2
        target = userid if chat_type == 1 else chatid
        # 记录会话，用于后续主动推送
        self._user_chat = (target, chat_type, userid)
        self._chat_event.set()
        print(f"[企微] 收到 {msgtype} 消息，来自 {userid}（{'单聊' if chat_type == 1 else '群聊'}，target={target}）")

        cb = self._callbacks.get(msgtype) or self._callbacks.get("*")
        if cb:
            try:
                cb(body)
            except Exception as e:
                print(f"[企微] 回调异常: {e}")
        else:
            # 首次发消息时引导
            self.send_text(target, chat_type, "✅ 已连接，请按快捷键截图提问～")

    def on_message(self, msgtype):
        """装饰器：注册某 msgtype 的回调。"""
        def decorator(func):
            self._callbacks[msgtype] = func
            return func
        return decorator

    # ---------- 发消息 ----------
    def send_text(self, target, chat_type, text) -> None:
        # aibot_send_msg 响应延迟大且不可靠，fire-and-forget 不阻塞
        self._send_frame("aibot_send_msg", {
            "chatid": target, "chat_type": chat_type,
            "msgtype": "text", "text": {"content": text},
        })

    def send_markdown(self, target, chat_type, content) -> None:
        self._send_frame("aibot_send_msg", {
            "chatid": target, "chat_type": chat_type,
            "msgtype": "markdown", "markdown": {"content": content},
        })

    def upload_media(self, data: bytes, media_type: str = "image", filename: str = "image.png") -> str:
        """分片上传临时素材，返回 media_id（3 天有效）。"""
        md5 = hashlib.md5(data).hexdigest()
        chunk_size = 512 * 1024  # base64 编码前 ≤ 512KB
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

        init = self._request("aibot_upload_media_init", {
            "type": media_type, "filename": filename,
            "total_size": len(data), "total_chunks": len(chunks), "md5": md5,
        })
        if self._debug:
            print(f"[企微 debug] upload_init 响应: {init}")
        upload_id = init.get("upload_id")
        if not upload_id:
            print(f"[企微] 上传初始化失败（未拿到 upload_id）: {init}")
            return ""

        for i, chunk in enumerate(chunks):
            self._request("aibot_upload_media_chunk", {
                "upload_id": upload_id, "chunk_index": i,
                "base64_data": base64.b64encode(chunk).decode("ascii"),
            })

        finish = self._request("aibot_upload_media_finish", {"upload_id": upload_id})
        if self._debug:
            print(f"[企微 debug] upload_finish 响应: {finish}")
        return finish.get("media_id", "")

    def send_image(self, target, chat_type, data: bytes, filename: str = "screenshot.png") -> None:
        """上传图片并主动发送到指定会话。"""
        media_id = self.upload_media(data, "image", filename)
        if not media_id:
            print("[企微] 无 media_id，跳过发送图片")
            return
        # 发图片消息，fire-and-forget（响应不可靠，看企微端是否收到即可）
        self._send_frame("aibot_send_msg", {
            "chatid": target, "chat_type": chat_type,
            "msgtype": "image", "image": {"media_id": media_id},
        })
        if self._debug:
            print(f"[企微 debug] 已发送图片请求 (media_id={media_id[:16]}...)")

    # ---------- 会话管理 ----------
    def get_user_chat(self):
        return self._user_chat

    def wait_for_chat(self, timeout=None):
        """阻塞等待用户首次给机器人发消息。"""
        if self._chat_event.wait(timeout):
            return self._user_chat
        return None
