"""MouseFox GUI app."""

from typing import Optional, Literal
from loguru import logger
import asyncio
import functools
import pathlib
import kvex as kx
import kvex.kivy
import pgnet
from .connectframe import ConnectionFrame
from .serverframe import ServerFrame
from .. import util


HOTKEYS_FILE = pathlib.Path(__file__).parent / "hotkeys.toml"
MINIMUM_SIZE = (1024, 768)


class App(kx.XApp):
    def __init__(
        self,
        *,
        game_widget: kvex.kivy.Widget,
        client_cls: Optional[pgnet.BaseClient] = None,
        localhost_cls: Optional[pgnet.BaseClient] = None,
        maximize: bool = True,
        borderless: bool = False,
        size: Optional[tuple[int, int]] = None,
        offset: Optional[tuple[int, int]] = None,
        title: str = "MouseFox",
    ):
        super().__init__()
        self._client: Optional[pgnet.BaseClient] = None
        if borderless:
            self.toggle_borderless(True)
        if size:
            size = tuple(max(c) for c in zip(MINIMUM_SIZE, size))
            self.set_size(*size)
        else:
            self.set_size(*MINIMUM_SIZE)
        if offset:
            kx.schedule_once(lambda *a: self.set_position(*offset))
        if maximize:
            kx.schedule_once(lambda *a: self.maximize())
        self.title = title
        self.controller = kx.XHotkeyController(
            logger=logger.debug,
            log_register=True,
            log_bind=True,
            log_callback=True,
        )
        self._register_controller(self.controller)
        self._make_menu()
        self.connection_frame = ConnectionFrame(
            client_cls=client_cls,
            localhost_cls=localhost_cls,
        )
        self.server_frame = ServerFrame(game_widget)
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
        controller.bind("disconnect", self._disconnect)

    def _make_menu(self):
        self.menu = kx.XButtonBar()
        self.menu.set_size(x="500dp")
        self.menu.add_category("app")
        self.menu.add_category("server")
        self.menu.add_button("app", "quit", self.stop)
        self.menu.add_button("app", "restart", self.restart)
        self.menu.add_button("server", "disconnect", self._disconnect)

    def make_widgets(self):
        self.root.clear_widgets()
        self.root.make_bg(kx.get_color("purple", v=0.05))
        self._status = kx.XLabel(halign="left", italic=True, padding=(10, 0))
        top_bar = kx.XBox()
        top_bar.add_widgets(self.menu, self._status)
        top_bar.set_size(y="32dp")
        top_bar.make_bg(kx.get_color("purple", v=0.2))
        self.main_frame = kx.XAnchor()
        root_frame = kx.XBox(orientation="vertical")
        root_frame.add_widgets(top_bar, self.main_frame)
        self.root.add_widget(root_frame)
        self.show_connection_screen()

    def show_connection_screen(self):
        self.menu.get_button("server").disabled = True
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.connection_frame)
        self.connection_frame.set_focus()
        self.controller.set("connection")

    def show_server_screen(self, client):
        client.on_connection = None
        self.menu.get_button("server").disabled = False
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.server_frame)
        self.server_frame.set_client(client)
        self.controller.set("server.lobby")

    def update(self, *args):
        self.server_frame.update()

    def set_feedback(
        self,
        text: str,
        stype: Literal["normal", "warning", "error"] = "normal",
        /,
    ):
        self._status.text = text
        if stype == "normal":
            color = 0.8, 0.8, 0.8
        elif stype == "warning":
            color = 1, 0.4, 0
        elif stype == "error":
            color = 1, 0.2, 0.2
        else:
            raise ValueError("Unknown status type.")
        self._status.color = color

    def set_client(self, client: pgnet.BaseClient, /):
        asyncio.create_task(self._async_set_client(client))

    async def _async_set_client(self, client: pgnet.BaseClient, /):
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
        self.set_feedback(status, "normal" if client.connected else "error")

    def _disconnect(self, *args):
        if self._client:
            self._client.close()
        self.show_connection_screen()

    async def async_run(self):
        r = await super().async_run()
        if self._client:
            self._client.close()
        return r


def _flatten_hotkey_paths(nested: dict, prefix: str = "") -> dict:
    new_dict = dict()
    for k, v in nested.items():
        if isinstance(v, dict):
            new_dict |= _flatten_hotkey_paths(v, f"{prefix}{k}.")
        else:
            new_dict[f"{prefix}{k}"] = v
    return new_dict
