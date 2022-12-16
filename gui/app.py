
from typing import Optional
from loguru import logger
import asyncio
import functools
import pathlib
import kex as kx
import gui.connectframe
import gui.serverframe
import logic.client
import util


HOTKEYS_FILE = pathlib.Path(__file__).parent / "hotkeys.toml"
MINIMUM_SIZE = (1024, 768)


def _flatten_hotkey_paths(nested: dict, prefix: str = "") -> dict:
    new_dict = dict()
    for k, v in nested.items():
        if isinstance(v, dict):
            new_dict |= _flatten_hotkey_paths(v, f"{prefix}{k}.")
        else:
            new_dict[f"{prefix}{k}"] = v
    return new_dict


class App(kx.XApp):
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
            self.toggle_borderless(True)
        if maximize:
            self.maximize()
        else:
            if size:
                size = tuple(max(c) for c in zip(MINIMUM_SIZE, size))
                self.set_size(*size)
            if offset:
                kx.schedule_once(lambda *a: self.set_position(*offset))
        self.title = "KPdemo"
        self.controller = kx.XHotkeyController(
            logger=logger.debug,
            log_register=True,
            log_bind=True,
            log_callback=True,
        )
        self._register_controller(self.controller)
        self.make_widgets()
        self.hook(self.update, 20)
        self.set_feedback("Welcome")

    def _register_controller(self, controller: kx.XHotkeyController):
        loaded_dict = util.toml_load(HOTKEYS_FILE)
        hotkeys = _flatten_hotkey_paths(loaded_dict)
        for control, hotkeys in hotkeys.items():
            if not isinstance(hotkeys, list):
                hotkeys = [hotkeys]
            for hk in hotkeys:
                controller.register(control, hk)
        controller.bind("quit", self.stop)
        controller.bind("restart", self.restart)
        controller.bind("debug", controller.debug)

    def make_widgets(self):
        self.root.clear_widgets()
        self.root.make_bg(kx.get_color("purple", v=0.05))
        self.connection_frame = gui.connectframe.ConnectionFrame()
        self.server_frame = gui.serverframe.ServerFrame()
        self.main_frame = kx.XAnchor()
        self.status_bar = kx.XLabel(halign="left", italic=True, padding=(10, 0))
        self.status_bar.set_size(y=40)
        self.status_bar.make_bg(kx.get_color("purple", v=0.2))
        root_frame = kx.XBox(orientation="vertical")
        root_frame.add_widgets(self.main_frame, self.status_bar)
        self.root.add_widget(root_frame)
        self.show_connection_screen()

    def show_connection_screen(self):
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.connection_frame)
        self.controller.set("connection")

    def show_server_screen(self, client):
        client.on_connection = None
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.server_frame)
        self.server_frame.set_client(client)
        self.controller.set("server.lobby")

    def update(self, *args):
        self.server_frame.update()

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
        self.set_feedback(client.status)
        client.on_connection = lambda *args: self.show_server_screen(client)
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
