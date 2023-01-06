"""MouseFox GUI app."""

from typing import Optional, Literal, Type, Callable
from loguru import logger
import asyncio
from dataclasses import dataclass
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


@dataclass
class AppConfig:
    """Configuration for MouseFox app."""

    game_widget: kvex.kivy.Widget
    """Kivy widget for the game."""
    game_class: Type[pgnet.Game]
    """Game subclass for the local client and server (see `pgnet.Server`)."""
    client_class: Type[pgnet.Client] = pgnet.Client
    """Client subclass for the client (see `pgnet.Client`)."""
    server_factory: Optional[Callable] = None
    """The server factory for the local client (see `pgnet.Client.local`)."""
    disable_local: bool = False
    """Disable local clients."""
    disable_remote: bool = False
    """Disable remote clients."""
    maximize: bool = False
    """If app should start maximized."""
    borderless: bool = False
    """If app should not have window borders."""
    size: Optional[tuple[int, int]] = None
    """App window size in pixels."""
    offset: Optional[tuple[int, int]] = None
    """App window offset in pixels."""
    title: str = "MouseFox"
    """App window title."""
    info_text: str = "No info available."
    """Text to show when ready to connect."""
    online_info_text: str = "No online info available."
    """Text to show when ready to connect remotely."""
    allow_quit: bool = True
    """Allow MouseFox to quit or restart the script."""

    def __getitem__(self, item):
        """Get item."""
        return getattr(self, item)

    def keys(self):
        """Enables mapping.

        For example:
        ```python3
        config = mousefox.AppConfig(...)
        mousefox.run(**config)
        ```
        """
        return self.__dataclass_fields__.keys()


class App(kx.XApp):
    """MouseFox GUI app."""

    def __init__(self, app_config: AppConfig, /):
        """Initialize the app. It is recommended to run the app with `mousefox.run`."""
        super().__init__()
        self._client: Optional[pgnet.Client] = None
        if app_config.borderless:
            self.toggle_borderless(True)
        if app_config.size:
            size = tuple(max(c) for c in zip(MINIMUM_SIZE, app_config.size))
            self.set_size(*size)
        else:
            self.set_size(*MINIMUM_SIZE)
        if app_config.offset:
            kx.schedule_once(lambda *a: self.set_position(*app_config.offset))
        if app_config.maximize:
            kx.schedule_once(lambda *a: self.maximize())
        self.title = app_config.title
        """App title."""
        self.controller = kx.XHotkeyController(
            logger=logger.debug,
            log_register=True,
            log_bind=True,
            log_callback=True,
        )
        self.game_controller = kx.XHotkeyController(
            logger=logger.debug,
            log_register=True,
            log_bind=True,
            log_callback=True,
        )
        self._register_controller(self.controller)
        self._make_menu()
        self.connection_frame = ConnectionFrame(app_config)
        self.server_frame = ServerFrame(app_config.game_widget)
        self._make_widgets()
        self.hook(self._update, 20)
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

    def _make_widgets(self):
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
        self._show_connection_screen()

    def _show_connection_screen(self):
        self.menu.get_button("server").disabled = True
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.connection_frame)
        self.connection_frame.set_focus()
        self.controller.set_active("connection")

    def _show_server_screen(self, client: pgnet.Client):
        client.on_connection = None
        self.menu.get_button("server").disabled = False
        self.main_frame.clear_widgets()
        self.main_frame.add_widget(self.server_frame)
        self.server_frame.set_client(client)
        self.controller.set_active("server.lobby")

    def _update(self, *args):
        self.server_frame.update()

    def set_feedback(
        self,
        text: str,
        stype: Literal["normal", "warning", "error"] = "normal",
        /,
    ):
        """Set feedback in the status bar.

        Args:
            text: Text to show.
            stype: Status type, used for colors.
        """
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

    def set_client(self, client: pgnet.Client, /):
        """Set a client for the app to use."""
        asyncio.create_task(self._async_set_client(client))

    async def _async_set_client(self, client: pgnet.Client, /):
        if self._client:
            self._client.disconnect()
        self._client = client
        client.on_status = functools.partial(self._on_client_status, client)
        self.set_feedback(client.status)
        client.on_connection = lambda *args: self._show_server_screen(client)
        await client.async_connect()

    def _on_client_status(self, client: pgnet.Client, status: str):
        if client is not self._client:
            logger.warning(f"Old client event.\n{client=}\n{self._client=}")
            return
        self.set_feedback(status, "normal" if client.connected else "error")

    def _disconnect(self, *args):
        if self._client:
            self._client.disconnect()
        self._show_connection_screen()

    async def async_run(self):
        """Override base method."""
        r = await super().async_run()
        if self._client:
            self._client.disconnect()
        await _close_remaining_tasks()
        return r


def _flatten_hotkey_paths(nested: dict, prefix: str = "") -> dict:
    new_dict = dict()
    for k, v in nested.items():
        if isinstance(v, dict):
            new_dict |= _flatten_hotkey_paths(v, f"{prefix}{k}.")
        else:
            new_dict[f"{prefix}{k}"] = v
    return new_dict


async def _close_remaining_tasks(debug: bool = True):
    remaining_tasks = asyncio.all_tasks() - {asyncio.current_task(), }
    if not remaining_tasks:
        return
    for t in remaining_tasks:
        t.cancel()
    if debug:
        logger.debug(
            f"Remaining {len(remaining_tasks)} tasks:\n"
            + "\n".join(f"  -- {t}" for t in remaining_tasks)
        )
    for coro in asyncio.as_completed(list(remaining_tasks)):
        try:
            await coro
        except asyncio.CancelledError:
            removed_tasks = remaining_tasks - asyncio.all_tasks()
            remaining_tasks -= removed_tasks
            if removed_tasks and not debug:
                logger.debug(f"Removed {len(removed_tasks)} tasks: {removed_tasks}")
                logger.debug(
                    f"Remaining {len(remaining_tasks)} tasks:\n"
                    + "\n".join(f"  -- {t}" for t in remaining_tasks)
                )
            continue
