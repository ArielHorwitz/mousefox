
from typing import Optional
from loguru import logger
import asyncio
import functools
import kex as kx
import gui.connectframe
import gui.serverframe
import logic.client


MINIMUM_SIZE = (1024, 768)


class App(kx.App):
    def __init__(
        self,
        maximize: bool = True,
        borderless: bool = False,
        size: Optional[tuple[int, int]] = None,
        offset: Optional[tuple[int, int]] = None,
    ):
        super().__init__()
        self._client: Optional[logic.client.Client] = None
        if borderless:
            kx.Window.toggle_borderless(True)
        if maximize:
            kx.Window.maximize()
        else:
            if size:
                size = tuple(max(c) for c in zip(MINIMUM_SIZE, size))
                kx.Window.set_size(*size)
            if offset:
                kx.schedule_once(lambda *a: kx.Window.set_position(*offset))
        self.title = "Multiplayer prototype"
        self.make_ims()
        self.make_widgets()
        self.set_feedback("Welcome")

    def make_ims(self):
        self.im = kx.InputManager("App")
        self.im.register("app.quit", self.stop, "^+ q")
        self.im.register("app.restart", self.restart, "^+ w")
        self.connection_im = kx.InputManager("Connection frame", active=False)
        self.server_im = kx.InputManager("Server frame", active=False)
        group = {
            "connect": [self.connection_im],
            "server": [self.server_im],
        }
        self.im_group = kx.InputManagerGroup(group, always_active=[self.im])

    def make_widgets(self):
        self.root.clear_widgets()
        self.root.make_bg(kx.get_color("purple", v=0.05))
        self.connection_frame = gui.connectframe.ConnectionFrame()
        self.server_frame = gui.serverframe.ServerFrame()
        self.main_frame = kx.Anchor()
        self.status_bar = kx.Label(
            halign="left",
            italic=True,
            padding=(10, 0),
        )
        self.status_bar.set_size(y=40)
        self.status_bar.make_bg(kx.get_color("purple", v=0.2))
        root_frame = kx.Box(orientation="vertical")
        root_frame.add(self.main_frame, self.status_bar)
        self.root.add(root_frame)
        self.show_connection_screen()

    def show_connection_screen(self):
        self.main_frame.clear_widgets()
        self.main_frame.add(self.connection_frame)
        self.im_group.switch("connect")

    def make_server_screen(self, client):
        self.main_frame.clear_widgets()
        self.main_frame.add(self.server_frame)
        self.server_frame.set_client(client)
        self.im_group.switch("server")

    def set_feedback(
        self,
        text: str,
        /,
        *,
        color: tuple[float, float, float] = (0.8, 0.8, 0.8),
    ):
        self.status_bar.text = text
        self.status_bar.color = (*color, 1)

    def set_feedback_warning(self, *args, **kwargs):
        self.set_feedback(*args, color=(1, 0.2, 0.2), **kwargs)

    def set_client(self, client: logic.client.Client, /):
        asyncio.create_task(self._async_set_client(client))

    async def _async_set_client(self, client: logic.client.Client, /):
        if self._client:
            self._client.close()
        self._client = client
        client.on_status = functools.partial(self._on_client_status, client)
        self.app.set_feedback(client.status)
        self.make_server_screen(client)
        await client.async_connect()

    def _on_client_status(self, client, status):
        if client is not self._client:
            logger.warning(f"Old client event.\n{client=}\n{self._client=}")
            return
        if client.connected:
            self.set_feedback(status)
        else:
            self.set_feedback_warning(status)

    async def async_run(self):
        r = await super().async_run()
        if self._client:
            self._client.close()
        return r
