"""MouseFox GUI app."""

from typing import Optional, Type, Callable
from loguru import logger
import asyncio
from dataclasses import dataclass
import pathlib
import kvex as kx
import kvex.kivy
import pgnet
from .. import util
from .clientframe import ClientFrame
from .serverframe import ServerFrame


COLOR_PALETTE = "default"
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
    size: Optional[tuple[int, int]] = (1280, 768)
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
            name="app",
            logger=logger.debug,
            log_register=True,
            log_bind=True,
            log_callback=True,
            log_active=True,
        )
        self._register_controller(self.controller)
        self.game_controller = kx.XHotkeyController(
            name="game",
            logger=logger.debug,
            log_register=True,
            log_bind=True,
            log_callback=True,
            log_active=True,
        )
        self._make_widgets(app_config)
        self.hook(self._update, 20)
        self.set_feedback("Welcome")

    async def async_run(self):
        """Override base method."""
        r = await super().async_run()
        if self._client:
            self._client.disconnect()
        await _close_remaining_tasks()
        return r

    def set_feedback(self, text: str, status: pgnet.Status = pgnet.Status.OK, /):
        """Set feedback in the status bar.

        Args:
            text: Text to show.
            status: pgnet.Status, used for colors.
        """
        color_name = "fg_warn" if status else "fg"
        self._status.color = self.theme.primary[color_name].rgba
        self._status.text = text

    def feedback_response(
        self,
        response: pgnet.Response,
        *,
        only_statuses: bool = True,
    ):
        """Send a response to status bar.

        Args:
            response: pgnet Response.
            only_statuses: Ignore responses with OK status.
        """
        if only_statuses and response.status == pgnet.Status.OK:
            return
        self.set_feedback(response.message, response.status)

    def _show_client(self, *args):
        self._sm.current = "client"
        self.controller.active = "client"
        self.menu.get_button("app", "host_server").disabled = False

    def _show_server(self, *args):
        self._sm.current = "server"
        self.controller.active = "server"
        self.menu.get_button("app", "host_server").disabled = True

    def _make_widgets(self, app_config):
        self._make_menu()
        self._status = kx.XLabel(
            halign="left",
            valign="middle",
            italic=True,
            padding=(10, 10),
        )
        self._client_frame = ClientFrame(app_config)
        self._server_frame = ServerFrame(app_config)
        self._sm = kx.XScreenManager.from_widgets(
            dict(
                client=self._client_frame,
                server=self._server_frame,
            ),
            transition=kx.FadeTransition(duration=0.2),
        )
        # Assemble
        self.top_bar = kx.XBox()
        self.top_bar.add_widgets(self.menu, self._status)
        self.top_bar.set_size(y="32sp")
        main_frame = kx.XBox(orientation="vertical")
        main_frame.add_widgets(self.top_bar, self._sm)
        self.root.clear_widgets()
        self.root.add_widget(main_frame)
        self._refresh_background()
        self._show_client()

    def on_theme(self, *args):
        """Override base method."""
        self.set_feedback(f"Set theme: {self.theme_name}")
        self._refresh_background()

    def _refresh_background(self, *args):
        self.root.make_bg(self.theme.primary.bg)

    def _make_menu(self):
        self.menu = kx.XButtonBar()
        self.menu.set_size(x="500dp")
        self.menu.add_category("app")
        menu_add = self.menu.add_button
        menu_add("app", "disconnect")
        menu_add("app", "leave_game")
        menu_add("app", "lobby")
        menu_add("app", "game")
        menu_add("app", "admin_panel")
        menu_add("app", "host_server", self._show_server)
        menu_add("app", "restart", self.restart)
        menu_add("app", "quit", self.stop)
        menu_get = self.menu.get_button
        menu_get("app", "lobby").disabled = True
        menu_get("app", "game").disabled = True
        menu_get("app", "admin_panel").disabled = True
        self.menu.add_theme_selectors(prefix="")

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
        controller.bind("show_client", self._show_client)
        controller.bind("show_server", self._show_server)
        for i, tname in enumerate(kx.THEME_NAMES):
            self.controller.register(
                f"Change theme to {tname}",
                f"numpad{i+1}",
                bind=lambda *a, t=tname: self.set_theme(t),
            )

    def _update(self, *args):
        self._client_frame.update()


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
