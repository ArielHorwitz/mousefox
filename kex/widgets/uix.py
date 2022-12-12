"""UI widgets."""
from typing import Optional, Any, Mapping
import re
from .. import kivy as kv
from ..util import XWidget, ColorType, XColor
from .layouts import XBox, XAnchor
from .input_manager import XInputManager


class XLabel(XWidget, kv.Label):
    """Label."""

    def __init__(self, fixed_width: bool = False, **kwargs):
        """Initialize the class.

        Args:
            fixed_width: Adjust the height of the label while maintaining width.
        """
        kwargs = {
            "markup": True,
            "halign": "center",
            "valign": "center",
        } | kwargs
        super().__init__(**kwargs)
        self._trigger_fix_height = kv.Clock.create_trigger(self._fix_height)
        if fixed_width:
            self.bind(
                size=self._trigger_fix_height,
                text=self._trigger_fix_height,
            )
        else:
            self.bind(size=self._on_size)

    def _fix_height(self, *a):
        x = self.size[0]
        hx = self.size_hint[0]
        self.text_size = x, None
        self.texture_update()
        if hx is None:
            self.set_size(x=x, y=self.texture_size[1])
        else:
            self.set_size(hx=hx, y=self.texture_size[1])

    def _on_size(self, *a):
        self.text_size = self.size


class XLabelClick(kv.ButtonBehavior, XLabel):
    """Label with ButtonBehavior."""

    pass


class XCheckBox(XWidget, kv.CheckBox):
    """CheckBox."""

    def toggle(self, *a):
        """Toggle the active state."""
        self.active = not self.active


class XButton(XWidget, kv.Button):
    """Button."""

    def __init__(
        self,
        background_color: ColorType = XColor.from_name("blue", 0.5).rgba,
        **kwargs,
    ):
        """Initialize the class.

        Args:
            background_color: Background color of the button.
        """
        kwargs = {
            "markup": True,
            "halign": "center",
            "valign": "center",
        } | kwargs
        super().__init__(**kwargs)
        self.background_color = background_color

    def on_touch_down(self, m):
        """Overrides base class method to only react to left clicks."""
        if m.button != "left":
            return False
        return super().on_touch_down(m)


class XToggleButton(kv.ToggleButtonBehavior, XButton):
    """ToggleButton."""

    active = kv.BooleanProperty(False)
    """Behaves like an alias for the `state` property being "down"."""

    def __init__(self, **kwargs):
        """Same arguments as kivy Button."""
        super().__init__(**kwargs)
        self.bind(state=self._set_active)
        self.bind(active=self._set_state)

    def toggle(self, *args):
        """Toggles the active state of the button."""
        self.active = not self.active

    def _set_state(self, *args):
        self.state = "down" if self.active else "normal"

    def _set_active(self, *args):
        self.active = self.state == "down"


class XImageButton(XWidget, kv.ButtonBehavior, kv.Image):
    """Image with ButtonBehavior mixin."""

    pass


class XEntryMixin:

    select_on_focus = kv.BooleanProperty(False)
    defocus_brightness = kv.NumericProperty(0.5)
    deselect_on_escape = kv.BooleanProperty(False)
    cursor_pause_timeout = kv.NumericProperty(0.5)
    cursor_scroll_offset = kv.NumericProperty(5)

    def __init__(self, *args, fix_scroll_to_line: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._background_color_focused = None
        self._background_color_unfocused = None
        self._refresh_background()
        self.register_event_type("on_cursor_pause")
        self._reset_cursor_pause_trigger()
        self.bind(
            cursor=self._on_cursor_for_pause,
            cursor_pause_timeout=self._reset_cursor_pause_trigger,
            defocus_brightness=self._refresh_background,
            focus=self._on_any_focus,
        )
        kv.Window.bind(focus=self._on_any_focus)
        if fix_scroll_to_line:
            self.bind(scroll_y=self._on_scroll_y, size=self._on_size_fix_scroll)

    def _refresh_background(self, *args):
        self.set_background()

    def set_background(self, color=None):
        """Set the background color (that will change based on `defocus_brightness`)."""
        if color is None:
            color = self._background_color_focused or self.background_color
        self._background_color_focused = XColor(*color).rgba
        self._background_color_unfocused = XColor(
            *self._background_color_focused,
            v=self.defocus_brightness,
        ).rgba
        self._on_any_focus()

    def visible_line_range(self):
        top_line = round(self.scroll_y / self.line_height)
        bot_line = top_line + int(self.height / self.line_height)
        return top_line, bot_line + 1

    def selected_line_range(self):
        if not self._selection:
            return self.cursor_row, self.cursor_row
        _, row_from = self.get_cursor_from_index(self._selection_from)
        _, row_to = self.get_cursor_from_index(self._selection_to)
        start, end = min(row_from, row_to), max(row_from, row_to)
        return start, end

    def scroll_to_cursor(self, *a):
        top_line = self.cursor[1] - self.cursor_scroll_offset
        # Don't overshoot last line
        visible_count = int(self.height / self.line_height)
        top_cap = len(self._lines) - visible_count + 1
        # Don't overshoot cursor out of view
        top_cap = min(self.cursor_row, top_cap)
        bot_cap = max(0, self.cursor_row - visible_count + 2)
        top_line = max(max(0, bot_cap), min(top_line, top_cap))
        self.scroll_y = self.line_height * top_line
        self.scroll_x = 0
        self._trigger_update_graphics()

    def _refresh_line_options(self, *args):
        """Override base method to prevent scroll reset."""
        prev_cur = self.cursor
        super()._refresh_line_options(*args)
        self.cursor = prev_cur

    def on_size(self, w, size):
        """Override base method to prevent scroll reset."""
        self._trigger_refresh_text()
        self._refresh_hint_text()
        self.scroll_to_cursor()

    def _reset_cursor_pause_trigger(self, *args):
        self.__trigger_cursor_pause = kv.Clock.create_trigger(
            lambda t: self.dispatch("on_cursor_pause"),
            self.cursor_pause_timeout,
        )

    def _on_textinput_focused(self, w, focus):
        """Overrides base method to handle changing focus.

        Selects all text when focused, changes brightness, and
        fixes base class bugs relating to modifiers.
        """
        self._fix_textinput_modifiers()
        super()._on_textinput_focused(w, focus)
        if focus and self.select_on_focus:
            self.select_all()

    def _fix_textinput_modifiers(self):
        self._ctrl_l = False
        self._ctrl_r = False
        self._alt_l = False
        self._alt_r = False

    def _on_any_focus(self, *args):
        focus = kv.Window.focus and self.focus
        if focus:
            self.background_color = self._background_color_focused
        else:
            self.background_color = self._background_color_unfocused

    def reset_cursor_selection(self, *a):
        """Resets the cursor position and selection."""
        self.cancel_selection()
        self.cursor = 0, 0
        self.scroll_x = 0
        self.scroll_y = 0

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        """Override base method to deselect instead of defocus on escape."""
        key, _ = keycode
        r = super().keyboard_on_key_down(window, keycode, text, modifiers)
        # Handle escape
        if key == 27:
            if not self.deselect_on_escape:
                self.cancel_selection()
                self.focus = True
        return r

    def _on_cursor_for_pause(self, w, cursor):
        ev = self.__trigger_cursor_pause
        if ev.is_triggered:
            ev.cancel()
        ev()

    def on_cursor_pause(self):
        pass

    def cancel_cursor_pause(self, *a):
        ev = self.__trigger_cursor_pause
        if ev.is_triggered:
            ev.cancel()

    def _on_size_fix_scroll(self, *args):
        kv.Clock.schedule_once(self.fix_scroll_to_line)

    def fix_scroll_to_line(self, *args):
        line = round(self.scroll_y / self.line_height)
        self.scroll_y = line * self.line_height

    def _on_scroll_y(self, w, scroll_y):
        self.fix_scroll_to_line()
        return True


class XEntry(XEntryMixin, XWidget, kv.TextInput):
    """TextInput with sane defaults."""

    def __init__(
        self,
        multiline: bool = False,
        background_color: list[float] = (0.2, 0.2, 0.2, 1),
        foreground_color: list[float] = (1, 1, 1, 1),
        disabled_foreground_color: list[float] = (0.5, 0.5, 0.5, 0.5),
        text_validate_unfocus: bool = True,
        write_tab: bool = False,
        **kwargs,
    ):
        """Initialize the class.

        Args:
            multiline: If should allow multiple lines.
            background_color: Color of the background.
            foreground_color: Color of the foreground.
            disabled_foreground_color: Color of the foreground when disabled.
            text_validate_unfocus: If focus should be removed after validation
                (pressing enter on a single-line widget).
            write_tab: Allow tabs to be written.
            kwargs: keyword arguments for TextInput.
        """
        super().__init__(
            background_color=background_color,
            foreground_color=foreground_color,
            disabled_foreground_color=disabled_foreground_color,
            multiline=multiline,
            text_validate_unfocus=text_validate_unfocus,
            write_tab=write_tab,
            **kwargs,
        )


RE_LEADING_WS = re.compile(r"^\s*")  # noqa: W605


class XCodeEntry(XEntryMixin, XWidget, kv.CodeInput):
    """CodeInput with modifications."""

    soft_tab = kv.BooleanProperty(True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, fix_scroll_to_line=True, **kwargs)
        kv.Window.bind(focus=self._on_window_focus)
        self.cursor_width = "2sp"
        self.cursor_color = 1, 1, 0, 1

    def _get_line_options(self):
        kw = super()._get_line_options()
        kw['style_name'] = self.style_name
        return kw

    def _on_window_focus(self, w, focus):
        self.cursor_blink = focus

    def insert_text(self, substring, *args, **kwargs):
        if substring == "\t" and self.soft_tab:
            substring = " " * self.tab_width
        super().insert_text(substring, *args, **kwargs)

    def duplicate(self):
        start, end = self.selected_line_range()
        lines = [""] + self._lines[start:end + 1]
        substring = "\n".join(lines)
        # Move cursor to end of last line
        self.cursor = len(self._lines[end]), end
        select_from = self.cursor_index() + 1
        # Paste
        self.insert_text(substring)
        select_to = self.cursor_index()
        # Select pasted lines
        self.select_text(select_from, select_to)

    def toggle_case(self, *args):
        text = self.selection_text
        if not text:
            return
        selection = self.selection_from, self.selection_to
        self.delete_selection()
        if text == text.upper():
            self.insert_text(text.lower())
        else:
            self.insert_text(text.upper())
        self.select_text(min(selection), max(selection))

    def join_split_lines_len(self, length: int = 80, sep: str = " "):
        start, end = self.selected_line_range()
        if start == end:
            self._split_line_len(start, length, sep)
        else:
            self._join_lines_len(start, end, sep)

    def _join_lines_len(self, start, end, sep):
        self.select_full_lines(start, end)
        text = self.selection_text
        self.delete_selection()
        ws = " " * len(re.match(" *", text).group())
        new_text = ws + sep.join(line.strip() for line in text.split("\n"))
        self.insert_text(new_text)
        self.select_full_lines(start, start)

    def _split_line_len(self, line, length, sep):
        self.select_full_lines(line, line)
        text = self.selection_text
        self.delete_selection()
        text_parts = text.split(sep)
        ws = " " * len(re.match(" *", text).group())
        new_lines = [ws]
        sep_len = len(sep)
        while text_parts:
            next_part = text_parts.pop(0)
            if not next_part:
                continue
            last_line_size = len(new_lines[-1])
            len_after_add = last_line_size + sep_len + len(next_part)
            # If too long, start a new line unless it is already a new line
            if last_line_size and len_after_add > length:
                new_lines.append(ws)
            if len(new_lines[-1]) > 0:
                new_lines[-1] = f"{new_lines[-1]}{sep}{next_part}"
            else:
                new_lines[-1] = f"{ws}{next_part}"
        self.insert_text("\n".join(new_lines))
        self.select_full_lines(line, line + len(new_lines) - 1)

    def join_split_lines(self, *args):
        start, end = self.selected_line_range()
        if start == end:
            self._split_line(start)
            return
        else:
            self._join_lines(start, end)

    def _split_line(
        self,
        line: int,
        sep: str = ",",
        split_first: str = "(",
        split_last: str = ")",
    ):
        self.select_full_lines(line, line)
        text = self.selection_text
        if not any(p in text for p in (sep, split_first, split_last)):
            return
        ws_len = len(re.match(r" *", text).group())
        ws = " " * ws_len
        ws_indented = " " * (ws_len + 4)
        first_line, *lines = text.split(sep)
        if split_first in first_line:
            fsplit_index = first_line.index(split_first) + 1
            lines.insert(0, first_line[fsplit_index:])
            first_line = first_line[:fsplit_index]
        else:
            first_line = f"{first_line}{sep}"
        last_line = lines.pop()
        if split_last in last_line:
            lsplit_index = last_line.rfind(split_last)
            lines.append(last_line[:lsplit_index])
            last_line = last_line[lsplit_index:]
            last_line = f"{ws}{last_line}"
        lines = [f"{ws_indented}{_.strip()}{sep}" for _ in lines]
        final_lines = [first_line, *lines, last_line]
        final_text = "\n".join(final_lines)
        self.delete_selection()
        self.insert_text(final_text)
        self.select_full_lines(line, line + len(final_lines) - 1)

    def _join_lines(self, start: int, end: int, join_with: str = ", "):
        self.select_full_lines(start, end)
        text = self.selection_text
        first_line, *lines = text.split("\n")
        lines = [_.strip() for _ in lines]
        last_line = lines.pop()
        lines = [
            line.removesuffix(join_with).removesuffix(",")
            for line in lines
        ]
        reduced = join_with.join(lines)
        final_text = f"{first_line}{reduced}{last_line}"
        self.delete_selection()
        self.insert_text(final_text)
        self.select_full_lines(start, start)

    def shift_lines(self, direction: int):
        start, end = self.selected_line_range()
        # Shift up
        if direction < 0 and start > 0:
            self.select_full_lines(start - 1, end)
            lines = self.selection_text.split("\n")
            lines.append(lines.pop(0))
            final_text = "\n".join(lines)
            self.delete_selection()
            self.insert_text(final_text)
            self.select_full_lines(start - 1, end - 1)
            return
        # Shift down
        _, line_count = self.get_cursor_from_index(len(self.text) + 1)
        if direction > 0 and end < line_count:
            self.select_full_lines(start, end + 1)
            lines = self.selection_text.split("\n")
            lines.insert(0, lines.pop())
            final_text = "\n".join(lines)
            self.delete_selection()
            self.insert_text(final_text)
            self.select_full_lines(start + 1, end + 1)
            return

    def find_next(
            self,
            text: str,
            move_cursor: bool = True,
    ) -> Optional[tuple[int, int]]:
        if not text:
            return None
        text = re.escape(text)
        cursor = self.cursor_index()
        match = re.search(text, self.text[cursor:])
        wrap_offset = 0
        if match is None:
            wrap_offset = cursor
            match = re.search(text, self.text)
            if match is None:
                return None
        start, end = match.span()
        start, end = start + cursor - wrap_offset, end + cursor - wrap_offset
        if move_cursor:
            self.cursor = self.get_cursor_from_index(end)
            self.scroll_to_cursor()
            self.select_text(start, end)
        return start, end

    def find_prev(
        self,
        text: str,
        move_cursor: bool = True,
    ) -> Optional[tuple[int, int]]:
        if not text:
            return None
        text = re.escape(text)
        cursor = self.cursor_index() - 1
        matches = list(re.finditer(text, self.text[:cursor]))
        if not matches:
            matches = list(re.finditer(text, self.text))
            if not matches:
                return None
        match = matches[-1]
        start, end = match.span()
        if move_cursor:
            self.cursor = self.get_cursor_from_index(end)
            self.scroll_to_cursor()
            self.select_text(start, end)
        return start, end

    def toggle_prepend(self, prepend: str, /):
        cursor = self.cursor
        start, end = self.selected_line_range()
        self.select_full_lines(start, end)
        lines = self.selection_text.split("\n")
        rstripped_prepend = prepend.rstrip()
        prep_len = len(prepend)
        # Find lowest indentation as anchor for all lines
        leading_ws = (RE_LEADING_WS.match(line).group() for line in lines)
        prep_start = min(len(lws) for lws in leading_ws)
        lstripped_lines = [line[prep_start:] for line in lines]
        indent = " " * prep_start
        # Toggling on if not all lines start with the prepend
        toggle_on = False
        for lsline in lstripped_lines:
            empty_line = not lsline or lsline == rstripped_prepend
            prep = prepend if not empty_line else rstripped_prepend
            if not lsline.startswith(prep):
                toggle_on = True
        # Collect the modified lines with/without their respective prepend
        new_lines = []
        for lsline in lstripped_lines:
            empty_line = len(lsline) == 0
            if toggle_on:
                new_line = f"{prepend}{lsline}" if not empty_line else rstripped_prepend
            else:
                new_line = lsline[prep_len:] if not empty_line else ""
            new_lines.append(f"{indent}{new_line}")
        # Finally modify the text in the widget
        self.delete_selection()
        self.insert_text("\n".join(new_lines))
        self.select_full_lines(start, end)
        self.cursor = cursor

    def indent(self, *args):
        start, end = self.selected_line_range()
        for lidx in range(start, end + 1):
            if not self._lines[lidx]:
                continue
            self.cursor = 0, lidx
            self.insert_text("    ")
        self.select_full_lines(start, end)

    def dedent(self, *args):
        start, end = self.selected_line_range()
        lines = self._lines
        for lidx in range(start, end + 1):
            old_indent = self._re_whitespace.match(lines[lidx])
            if not old_indent:
                continue
            old_indent_size = old_indent.end() - old_indent.start()
            remove_indent = min(4, old_indent_size)
            self.select_text(
                self.cursor_index((0, lidx)),
                self.cursor_index((remove_indent, lidx)),
            )
            self.delete_selection()
        self.select_full_lines(start, end)

    def select_full_lines(self, start_row, end_row):
        start = self.cursor_index((0, start_row))
        end = self.cursor_index((len(self._lines[end_row]), end_row))
        self.cursor = self.get_cursor_from_index(end)
        self.select_text(start, end)

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        """Override base method to multiline indent on [shift] tab."""
        key, _ = keycode
        # Handle tab
        if key == 9:
            mods = set(modifiers) - {"numlock"}
            if mods == {"shift"}:
                self.dedent()
                return True
            else:
                if self.selection_text:
                    self.indent()
                    return True
        return super().keyboard_on_key_down(window, keycode, text, modifiers)


class XSlider(XWidget, kv.Slider):
    """Slider."""

    pass


class XSliderText(XBox):
    """Slider with Label."""

    def __init__(
        self,
        prefix: str = "",
        rounding: int = 3,
        box_kwargs: Optional[Mapping[str, Any]] = None,
        label_kwargs: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ):
        """Initialize the class.

        Args:
            prefix: Text to prefix the value presented in the label.
            rounding: How many decimal places to show.
            box_kwargs: Keyword arguments for XBox.
            label_kwargs: Keyword arguments for XLabel.
            kwargs: Keyword arguments for XSlider.
        """
        box_kwargs = {} if box_kwargs is None else box_kwargs
        label_kwargs = {} if label_kwargs is None else label_kwargs
        label_kwargs = {"halign": "left"} | label_kwargs
        slider_kwargs = {"cursor_size": (25, 25)} | kwargs
        super().__init__(**box_kwargs)
        self.rounding = rounding
        self.prefix = prefix
        self.label = XLabel(**label_kwargs)
        self.label.set_size(hx=0.2)
        self.slider = XSlider(**slider_kwargs)
        self.add(self.label)
        self.add(self.slider)
        self.slider.bind(value=self._set_text)
        self._set_text(self, self.slider.value)

    def _set_text(self, w, value):
        if isinstance(value, float):
            value = round(value, self.rounding)
        if value == round(value):
            value = int(value)
        self.label.text = str(f"{self.prefix}{value}")


class XSpinner(XWidget, kv.Spinner):
    """Spinner."""

    value = kv.StringProperty("")

    def __init__(self, update_main_text: bool = True, **kwargs):
        """Same keyword arguments for Spinner.

        Args:
            update_main_text: Update the button text based on the selected value.
        """
        super().__init__(**kwargs)
        self.update_main_text = update_main_text
        if update_main_text:
            self.text_autoupdate = True

    def on_select(self, data):
        """Overrides base method."""
        pass

    def _on_dropdown_select(self, instance, data, *largs):
        if self.update_main_text:
            self.text = data
        self.value = data
        self.is_open = False
        self.on_select(data)


class XDropDown(XWidget, kv.DropDown):
    """DropDown."""

    pass


class XPickColor(XBox):
    """Color picking widget."""

    color = kv.ObjectProperty(XColor(0.5, 0.5, 0.5, 1))

    def __init__(self, **kwargs):
        """Same keyword arguments for Slider."""
        super().__init__(orientation="vertical")
        self.set_size(x=300, y=100)
        update_color = self._update_from_sliders
        self.sliders = []
        for i, c in enumerate("RGBA"):
            slider_kwargs = {
                "range": (0, 1),
                "step": 0.01,
                "value_track": True,
                "value_track_color": XColor(**{c.lower(): 0.75}).rgba,
                "value_track_width": "6dp",
                "cursor_size": (0, 0),
            } | kwargs
            s = self.add(XSliderText(**slider_kwargs))
            s.slider.bind(value=update_color)
            self.sliders.append(s)
        self.r, self.g, self.b, self.a = self.sliders
        self.set_color(self.color)

    def set_color(self, color: XColor):
        """Set the current color."""
        self.r.slider.value = color.r
        self.g.slider.value = color.g
        self.b.slider.value = color.b
        self.a.slider.value = color.a

    def _update_from_sliders(self, *a):
        color = XColor(
            self.r.slider.value,
            self.g.slider.value,
            self.b.slider.value,
            self.a.slider.value,
        )
        is_bright = sum(color.rgb) > 1.5
        for s in self.sliders:
            s.label.color = (0, 0, 0, 1) if is_bright else (1, 1, 1, 1)
        self.make_bg(color)
        self.color = color


class XSelectColor(XLabelClick):
    """An XPickColor that drops down from an XLabelClick."""

    def __init__(
        self,
        prefix: str = "[u]Color:[/u]\n",
        show_color_values: bool = True,
        **kwargs,
    ):
        """Initialize the class.

        Args:
            prefix: Text to show before the RGB values.
            show_color_values: Show the RGB values of the current color.
            kwargs: Keyword arguments for the XLabelClick.
        """
        self.prefix = prefix
        self.show_color_values = show_color_values
        super().__init__(**kwargs)
        self.picker = XPickColor()
        self.dropdown = XDropDown(auto_width=False, on_dismiss=self._on_color)
        self.dropdown.set_size(*self.picker.size)
        self.dropdown.add(self.picker)
        self.picker.bind(size=lambda w, s: self.dropdown.set_size(*s))
        self.bind(on_release=self.dropdown.open)
        self.on_color()

    def _on_color(self, *args):
        color = self.picker.color
        self.make_bg(color)
        text = self.prefix
        if self.show_color_values:
            text += " , ".join(str(round(c, 2)) for c in color.rgba)
        self.text = text


class XScreen(XWidget, kv.Screen):
    """Screen that can only contain one widget."""

    def __init__(self, **kwargs):
        """Same arguments as Screen."""
        super().__init__(**kwargs)
        self.view = None

    def add(self, *args, **kwargs) -> XWidget:
        """Overrides base method to set the view."""
        self.view = super().add(*args, **kwargs)
        if len(self.children) > 1:
            raise RuntimeError(
                f"Cannot add more than 1 widget to XScreen: {self.children=}"
            )


class XScreenManager(XWidget, kv.ScreenManager):
    """ScreenManager with custom transition behavior."""

    transition_speed = kv.NumericProperty(0.4)

    def __init__(self, **kwargs):
        """Same arguments as for ScreenManager, minus transition."""
        if "transition" in kwargs:
            del kwargs["transition"]
        super().__init__(**kwargs)
        self.transition = kv.SlideTransition(
            direction="left",
            duration=self.transition_speed,
        )

    def add_screen(self, name: str, widget: XWidget) -> XScreen:
        """Add a screen."""
        screen = self.add(XScreen(name=name))
        screen.add(widget)
        return screen

    def switch_name(self, name: str) -> bool:
        """Switch to a screen by name."""
        if name == self.current:
            return True
        if self.mid_transition:
            return False
        if name not in self.screen_names:
            raise ValueError(f'Found no screen by name "{name}" in {self.screen_names}')
        old_index = self.screen_names.index(self.current)
        new_index = self.screen_names.index(name)
        dir = "left" if old_index < new_index else "right"
        self.transition = kv.SlideTransition(
            direction=dir,
            duration=self.transition_speed,
        )
        self.current = name
        return True

    @property
    def mid_transition(self) -> bool:
        """If there is a transition in progress."""
        return 0 < self.current_screen.transition_progress < 1

    @classmethod
    def from_widgets(cls, widgets: Mapping[str, XWidget], **kwargs) -> "XScreenManager":
        """Create an XScreenManager from a dictionary of screen names and widgets."""
        sm = cls(**kwargs)
        for n, w in widgets.items():
            screen = XScreen(name=n)
            screen.add(w)
            sm.add(screen)
        return sm


class XModalView(XWidget, kv.ModalView):
    pass


class XModal(XAnchor):
    """A XAnchor with an XInputManager that can de/attach to a container."""

    def __init__(self, container: XAnchor, name: str = "Unnamed", **kwargs):
        super().__init__(**kwargs)
        self.container = container
        self.im = XInputManager(name=name, active=False)
        self.im.register("Dismiss", self.dismiss, "escape", consume_keys=False)
        self.bind(parent=self._on_parent)

    def toggle(self, *args, set_as: Optional[bool] = None):
        if set_as is None:
            set_as = self.parent is None
        if set_as:
            self.open()
        else:
            self.dismiss()

    def open(self, *args):
        if self.parent is not None:
            return
        self.container.add_widget(self)

    def dismiss(self, *args):
        if self.parent is None:
            return
        self.container.remove_widget(self)

    def _on_parent(self, w, parent):
        self.im.active = parent is not None
