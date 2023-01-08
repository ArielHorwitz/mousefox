"""Home of `AdminFrame`."""

import arrow
import json
import kvex as kx
import pgnet
import pprint


_STATUSES = {s.value: s for s in pgnet.Status}


class AdminFrame(kx.XAnchor):
    """Widget for admin controls."""

    def __init__(self, client: pgnet.Client):
        """Initialize the class with a client."""
        super().__init__()
        self._client = client
        self._make_widgets()
        self.app.controller.set_active_callback("client.admin", self.set_focus)

    def _make_widgets(self):
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
        self.response_label = kx.XLabel(
            font_name="RobotoMono-Regular",
            padding=(10, 10),
            halign="left",
            valign="top",
            fixed_width=True,
        )
        self.response_payload_label = kx.XLabel(
            font_name="RobotoMono-Regular",
            padding=(10, 10),
            halign="left",
            valign="top",
            fixed_width=True,
        )
        self.response_label_frame = kx.XScroll(view=self.response_label)
        self.response_label_frame.set_size(hy=0.5)
        self.response_payload_label_frame = kx.XScroll(view=self.response_payload_label)
        self.response_payload_label_frame.make_bg(kx.get_color("white", v=0.1))
        main_frame = kx.XBox(orientation="vertical")
        main_frame.add_widgets(
            title,
            self.packet_input,
            self.response_label_frame,
            self.response_payload_label_frame,
        )
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
            f"Message: [color=#ff33ff]{response.message!r}[/color]",
            f"Created: [color=#7777ff]{timestr}[/color]",
            f"[color=#33dddd]{response.debug_repr}[/color]",
        ]
        self.response_label.text = "\n\n".join(debug_strs)
        payload_strs = []
        for k, v in response.payload.items():
            vstr = v if isinstance(v, str) else pprint.pformat(v)
            payload_strs.append(f"\n[b][u][color=#ff33ff]{k.upper()}[/color][/u][/b]")
            payload_strs.append(f"[color=#55ee55]{vstr}[/color]")
        self.response_payload_label.text = "\n\n".join(payload_strs)

    def set_focus(self, *args):
        """Focus input widget."""
        self.packet_input.set_focus("message")
