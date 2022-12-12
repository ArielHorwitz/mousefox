"""InputManager.

Characters representing the modifier keys:

- `^` Control
- `!` Alt
- `+` Shift
- `#` Super
"""

from typing import Callable, Union, TypeVar, Iterable, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from .. import kivy as kv
from ..util import (
    XWidget,
    _ping,
    _pong,
)


KEYCODE_TEXT = {v: k for k, v in kv.Keyboard.keycodes.items()}
KeysFormat = TypeVar("KeysFormat", bound=str)
"""A type alias for a string formatted as either: `f'{modifiers} {key}'` or `key`."""
MODIFIER_SORT = "^!+#"
MOD2KEY = {
    "ctrl": "^",
    "alt-gr": "!",
    "alt": "!",
    "shift": "+",
    "super": "#",
    "meta": "#",
    "control": "^",
    "lctrl": "^",
    "rctrl": "^",
    "lalt": "!",
    "ralt": "!",
    "lshift": "+",
    "rshift": "+",
    "numlock": "",
    "capslock": "",
}
KEY2MOD = {
    "^": "ctrl",
    "!": "alt",
    "+": "shift",
    "#": "super",
}


@dataclass(frozen=True, eq=True, order=True)
class KeyControl:
    """Represents a control for the `XInputManager`."""

    name: str
    """The name of this control (to be used for filtering)."""
    owner_name: str
    """Name of XInputManager that owns this KeyControl"""
    callback: Callable[[], None] = field(compare=False)
    """Function to call when this control is invoked."""
    keys: list[KeysFormat] = field(compare=False)
    """The keybind of this control."""
    allow_repeat: bool = field(default=False, compare=False)
    """Allow this control to be repeatedly invoked while holding down the keys."""
    consume_keys: bool = field(default=True, compare=False)
    """Consume the keys (prevent others from seeing the keys)."""

    def __repr__(self):
        """Representation of the control."""
        keys = '", "'.join(self.keys)
        keys = f'"{keys}"'
        meta = []
        if self.allow_repeat:
            meta.append("repeatable")
        if self.consume_keys:
            meta.append("consumes")
        if meta:
            meta = ", ".join(meta)
            meta = f" ({meta})"
        meta = meta or ""
        return f"<KeyControl {self.owner_name}: {self.name}{meta} {keys}>"


def _format_keys(
    modifiers: list[str],
    key_name: str,
    honor_numlock: bool = True,
) -> KeysFormat:
    """Convert a combination of keys to a standard string format."""
    if (
        honor_numlock
        and "numlock" in modifiers
        and key_name.startswith("numpad")
        and len(key_name) == 7
    ):
        key_name = key_name[-1]
    # Remove duplicate modifiers
    modifiers = set(MOD2KEY[mod] for mod in modifiers)
    modifiers -= {""}
    # Remove modifier if it is the main key being pressed
    # e.g. when key_name == "lctrl", "ctrl" will be in modifiers
    if key_name in MOD2KEY:
        modifiers -= {MOD2KEY[key_name]}
    # No space required if no modifiers
    if len(modifiers) == 0:
        return key_name
    # Order of modifiers should be consistent
    sorted_modifiers = sorted(modifiers, key=lambda x: MODIFIER_SORT.index(x))
    # Return the KeysFormat
    mod_str = "".join(sorted_modifiers)
    return f"{mod_str} {key_name}"


def _fix_modifier_order(k: str) -> str:
    if " " not in k:
        return k
    mods, key = k.split(" ")
    sorted_mods = "".join(sorted(mods, key=lambda x: MODIFIER_SORT.index(x)))
    return f"{sorted_mods} {key}"


def humanize_keys(keys: KeysFormat) -> str:
    """Return a more human-readable string from a KeysFormat."""
    mods, key = keys.split(" ") if " " in keys else ([], keys)
    dstr = [KEY2MOD[mod] for mod in mods]
    dstr.append(key)
    return " + ".join(dstr)


class XInputManager(XWidget, kv.Widget):
    """See module documentation for details."""

    active = kv.BooleanProperty(True)
    """If the InputManager is active."""
    log_register = kv.BooleanProperty(False)
    """If registrations should be logged."""
    log_press = kv.BooleanProperty(False)
    """If key presses should be logged."""
    log_release = kv.BooleanProperty(False)
    """If key released should be logged."""
    log_callback = kv.BooleanProperty(False)
    """If invocations should be logged."""
    pressed = kv.StringProperty(" ")
    """Last keys that were pressed."""
    released = kv.StringProperty(" ")
    """Last keys that were released."""
    min_cooldown = kv.NumericProperty(0)
    """Minimum cooldown in milliseconds between invocations.

    This will ultimately be limited by the system's "repeat rate" of the
    keyboard. Setting a negative value will disable repeating.
    """
    honor_numlock = kv.BooleanProperty(True)
    """Consider numpad keys as different than number keys when numlock is disabled."""
    allow_overwrite = kv.BooleanProperty(False)
    """Allow overwriting existing controls."""
    humanize = humanize_keys
    """Alias for `humanize_keys`."""

    _all_hotkeys = []
    _currently_active_hotkeys = []

    @classmethod
    def get_all_hotkeys(cls):
        """Get KeyControls of all XInputManagers.

        Instead of caching instances of input managers which may disrupt garbage
        collection, we use the Window.on_key_down event and let each input manager
        handle the event to add their key controls to a class variable list.
        """
        cls._all_hotkeys = []
        # Dispatch a fake "meta" key press with special codepoint to call all IMs
        kv.Window.dispatch("on_key_down", 309, 225, "COLLECT_ACTIVE_HOTKEYS", ["meta"])
        r, cls._all_hotkeys = cls._all_hotkeys, []
        return r

    @classmethod
    def get_currently_active_hotkeys(cls) -> list[KeyControl]:
        """Like XInputManager.get_all_hotkeys but only for active input managers."""
        cls._currently_active_hotkeys = []
        # Dispatch a fake "meta" key press with special codepoint to call all IMs
        kv.Window.dispatch("on_key_down", 309, 225, "COLLECT_ACTIVE_HOTKEYS", ["meta"])
        r, cls._currently_active_hotkeys = cls._currently_active_hotkeys, []
        return r

    def __init__(
        self,
        name: str = "Unnamed",
        logger: Callable[[str], None] = print,
        *,
        bind_to_window: bool = True,
        **kwargs,
    ):
        """Class for managing key press bindings and hotkeys.

        Args:
            name: Arbitrary name of the object. Used for debugging.
            logger: Function to be used for logging.
            bind_to_window: Only set to False if you wish to manually bind key events.
        """
        self.name = name
        self.controls = {}
        self.control_keys = defaultdict(set)
        super().__init__(**kwargs)
        self.__last_down_ping = _ping() - self.min_cooldown
        self.logger = logger
        if bind_to_window:
            kv.Window.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)

    # Control management
    def register(
        self,
        name: str,
        callback: Callable[[], None],
        keys: Union[KeysFormat, list[KeysFormat]],
        allow_repeat: bool = False,
        consume_keys: bool = True,
    ):
        """Register or modify a control.

        Args:
            name: Control name.
            callback: Function to call when the control is invoked.
            keys: Keypresses that will invoke the control.
            allow_repeat: Allow this control to be repeatedly invoked if the
                keys have not been released.
            consume_keys: Consume the keys.
        """
        keys = [keys] if isinstance(keys, str) else keys
        keys = [_fix_modifier_order(k) for k in keys]
        kc = KeyControl(name, self.name, callback, keys, allow_repeat, consume_keys)
        if kc.name in self.controls:
            if not self.allow_overwrite:
                raise ValueError(
                    f"{kc.name} in {self.name} already exists, enable allow_overwrite "
                    "or use a unique name."
                )
            old_kc = self.controls[kc.name]
            if self.log_register:
                self.logger(f"{self.name} replacing {old_kc} -> {kc}")
            self._remove_kc(old_kc)
        else:
            if self.log_register:
                self.logger(f"{self.name} registering {kc}")
        self._register_kc(kc)

    def remove(self, name: str):
        """Remove a control by *name*."""
        if name not in self.controls:
            self.logger(f"{self.name} cannot remove non-existant control: {name}")
            return
        kc = self.controls[name]
        if self.log_register:
            self.logger(f"{self.name} removing {kc}")
        self._remove_kc(kc)

    def remove_all(self):
        """Remove all controls."""
        self.controls = {}
        self.control_keys = defaultdict(set)

    def _register_kc(self, kc: KeyControl):
        self.controls[kc.name] = kc
        for kf in kc.keys:
            self.control_keys[kf].add(kc)

    def _remove_kc(self, kc: KeyControl):
        for kf in kc.keys:
            self.control_keys[kf].remove(kc)
        del self.controls[kc.name]

    # Properties
    @property
    def humanized(self) -> str:
        """Return a more human-readable string of last pressed keys."""
        return humanize_keys(self.pressed)

    @property
    def on_cooldown(self) -> bool:
        """Check if we are on cooldown for repeating a key down event."""
        if self.min_cooldown < 0:
            return True
        return _pong(self.__last_down_ping) < self.min_cooldown

    @property
    def pressed_key(self) -> str:
        """The last pressed key."""
        return self.pressed.split(" ")[1] if " " in self.pressed else self.pressed

    @property
    def pressed_mods(self) -> str:
        """The last pressed modifiers."""
        kf = self.pressed
        if " " in kf:
            mods, key = kf.split(" ")
            mods = list(mods)
        else:
            mods, key = [], kf
        if key in MOD2KEY:
            extra_mod = MOD2KEY[key]
            if extra_mod not in mods:
                mods.append(extra_mod)
        sorted_mods = sorted(mods, key=lambda x: MODIFIER_SORT.index(x))
        return "".join(sorted_mods)

    def __repr__(self):
        """Repr."""
        cooldown = (
            f" {self.min_cooldown}ms cd" if self.min_cooldown >= 0 else " no repeat"
        )
        active = "" if self.active else " INACTIVE"
        return (
            f"<{self.name} InputManager, {len(self.controls)} controls "
            f"on {len(self.control_keys)} hotkeys{cooldown} {active}>"
        )

    # Kivy key press management
    def _on_key_down(
        self,
        window,
        key: int,
        scancode: int,
        codepoint: str,
        modifiers: list[str],
    ):
        if codepoint == "COLLECT_ACTIVE_HOTKEYS":
            self.__collect_hotkeys()
            return
        if not self.active or self._app_blocked:
            return
        key_name = KEYCODE_TEXT.get(key, "")
        kf = _format_keys(modifiers, key_name, self.honor_numlock)
        is_repeat = kf == self.pressed
        if is_repeat and self.on_cooldown:
            return
        self.__last_down_ping = _ping()
        if not is_repeat and self.log_press:
            self.logger(
                f"Pressed:  |{kf}| {self}"
                f" ({key=} {scancode=} {codepoint=} {modifiers=})"
            )
        consumed = False
        if kf in self.control_keys:
            for kc in self.control_keys[kf]:
                if is_repeat and not kc.allow_repeat:
                    continue
                self._invoke_kc(kc)
                if kc.consume_keys:
                    if self.log_callback:
                        self.logger(f"Consumed {kf!r} by {kc} {self}")
                    consumed = True
                    break
        self.pressed = kf
        return consumed

    def _on_key_up(self, window, key: int, scancode: int):
        self.released = self.pressed
        self.pressed = " "
        if not self.active or self._app_blocked:
            return
        if self.log_release:
            key_name = KEYCODE_TEXT.get(key, "")
            self.logger(f"Released: |{key_name}| {self}")

    def _invoke_kc(self, kc: KeyControl):
        callback = kc.callback
        if self.log_callback:
            self.logger(f"Invoking {kc} {callback=} {self}")
        callback()

    @property
    def _app_blocked(self):
        if self.app is not None:
            return self.app.block_input
        return False

    def __collect_hotkeys(self):
        self._all_hotkeys.extend(self.controls.values())
        if self.active:
            self._currently_active_hotkeys.extend(self.controls.values())


class XInputManagerGroup:
    def __init__(
        self,
        input_managers: dict[str, Iterable[XInputManager]],
        /,
        *,
        always_active: Optional[Iterable[XInputManager]] = None,
    ):
        self.__ims = {
            name: tuple(im for im in ims)
            for name, ims in input_managers.items()
        }
        self.__always_active = tuple(always_active or [])

    def switch(self, active_im: Optional[str] = None, /):
        """Switch all InputManagers inactive except the given InputManager."""
        for name, ims in self.__ims.items():
            active = name == active_im
            for im in ims:
                im.active = active
        for im in self.__always_active:
            im.active = True
