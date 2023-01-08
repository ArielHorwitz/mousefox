"""Home of `AdminFrame`."""

import arrow
import json
import kvex as kx
import pgnet
import pprint
from .palette import Palette


_STATUSES = {s.value: s for s in pgnet.Status}


class AdminFrame(kx.XAnchor):
    """Widget for admin controls."""

    _conpath = "client.user.admin"

    def __init__(self, client: pgnet.Client):
        """Initialize the class with a client."""
        super().__init__()
        self._client = client
        self._make_widgets()
        self.app.controller.set_active_callback(self._conpath, self.set_focus)
        self.app.controller.bind(f"{self._conpath}.focus", self.set_focus)

    def _make_widgets(self):
        self.make_bg(Palette.BG_BASE)
        title = kx.XLabel(text="Admin Panel", bold=True, font_size="36dp")
        title.set_size(y="40dp")
        packet_input_widgets = dict(
            message=kx.XInputPanelWidget(label="Message:", label_hint=0.2),
            payload=kx.XInputPanelWidget(label="Payload (json):", label_hint=0.2),
        )
        self.packet_input = kx.XInputPanel(
            packet_input_widgets,
            reset_text="",
            invoke_text="",
        )
        self.packet_input.bind(on_invoke=self._on_packet_input)
        self.packet_input.set_size(y="100dp")
        self.debug_label = kx.XLabel(
            font_name="RobotoMono-Regular",
            padding=(10, 10),
            halign="left",
            valign="top",
            fixed_width=True,
        )
        self.response_label = kx.XLabel(
            font_name="RobotoMono-Regular",
            padding=(10, 10),
            halign="left",
            valign="top",
            fixed_width=True,
        )
        response_label_frame = kx.XScroll(view=self.response_label)
        response_label_frame.make_bg(Palette.BG_ALT)
        debug_label_frame = kx.XScroll(view=self.debug_label)
        debug_label_frame.set_size(hx=0.5)
        debug_label_frame.make_bg(Palette.BG_ALT2)
        bottom_frame = kx.XBox()
        bottom_frame.add_widgets(response_label_frame, debug_label_frame)
        main_frame = kx.XBox(orientation="vertical")
        main_frame.add_widgets(title, self.packet_input, bottom_frame)
        self.add_widget(main_frame)

    def _on_packet_input(self, w, values):
        message = values["message"]
        payload_text = values["payload"]
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = dict()
        # Prefix with __pgnet__, use "." to escape
        if message.startswith("."):
            message = message[1:]
        else:
            message = f"__pgnet__.{message}"
        packet = pgnet.Packet(message, payload)
        self._client.send(packet, self._response_callback)
        self.packet_input.set_focus("message")

    def _response_callback(self, response: pgnet.Response):
        status = _STATUSES[response.status]
        status_color = {
            pgnet.Status.OK.value: "00ff00",
            pgnet.Status.UNEXPECTED.value: "bbbb00",
            pgnet.Status.BAD.value: "ff0000",
        }.get(status)
        timestr = arrow.get(response.created_on).to("local").format("HH:mm:ss MMM DD")
        debug_strs = [
            f"Status: [color=#{status_color}]{status.name} ({status.value})[/color]",
            f"Created: [color=#7777ff]{timestr}[/color]",
            f"[color=#33dddd]{response.debug_repr}[/color]",
        ]
        self.debug_label.text = "\n\n".join(debug_strs)
        response_strs = [
            f"[color=#ffff33]{response.message!r}[/color]",
        ]
        for k, v in response.payload.items():
            vstr = v if isinstance(v, str) else pprint.pformat(v, width=10_000)
            response_strs.append(f"\n[u][color=#ff33ff]{k}[/color][/u]")
            response_strs.append(f"[color=#55ee55]{vstr}[/color]")
        self.response_label.text = "\n".join(response_strs)

    def set_focus(self, *args):
        """Focus input widget."""
        self.packet_input.set_focus("message")
