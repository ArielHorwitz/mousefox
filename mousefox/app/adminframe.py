"""Home of `AdminFrame`."""

import arrow
import functools
import json
import kvex as kx
import pgnet
import pprint


_STATUSES = {s.value: s for s in pgnet.Status}


class AdminFrame(kx.XFrame):
    """Widget for admin controls."""

    _conpath = "client.user.admin"

    def __init__(self, client: pgnet.Client):
        """Initialize the class with a client."""
        super().__init__(frame=False, bg=False)
        self._client = client
        self._make_widgets()
        self.app.controller.set_active_callback(self._conpath, self.set_focus)
        self.app.controller.bind(f"{self._conpath}.focus", self.set_focus)
        self.app.controller.bind(f"{self._conpath}.debug", self._request_debug)

    def _make_widgets(self):
        with self.app.subtheme_context("accent"):
            title = kx.frame(
                kx.XLabel(text="Admin Panel", bold=True, font_size="36sp"),
                bg=True,
                frame=False,
                pad=False,
            )
            title.set_size(y="40sp")
        # Requests frame
        requests_placeholder = kx.XPlaceholder(
            button_text="Get requests",
            callback=self._refresh_requests,
        )
        self.requests_frame = kx.XContainer(requests_placeholder)
        custom_input_label = kx.XLabel(
            text="Custom packet builder",
            bold=True,
            underline=True,
            font_size="18dp",
        )
        custom_input_title = kx.pad(custom_input_label)
        custom_input_title.set_size(y="40dp")
        packet_input_widgets = dict(
            message=kx.XInputPanelWidget(
                label="Message:",
                label_hint=0.2,
                orientation="vertical",
            ),
            payload=kx.XInputPanelWidget(
                label="Payload JSON:",
                label_hint=0.2,
                orientation="vertical",
            ),
        )
        self.packet_input = kx.XInputPanel(
            packet_input_widgets,
            reset_text="",
            invoke_text="Send packet",
        )
        self.packet_input.bind(on_invoke=self._on_packet_input)
        self.packet_input.set_size(y="100dp")
        custom_packet_frame = kx.XDynamicBox(orientation="vertical")
        custom_packet_frame.add_widgets(custom_input_title, self.packet_input)
        self.custom_packet_frame = kx.XDynamic(margin=True)
        self.custom_packet_frame.add_widget(custom_packet_frame)
        # Response labels
        self.response_label = kx.XLabel(
            font_name="RobotoMono-Regular",
            padding=(10, 10),
            halign="left",
            valign="top",
            fixed_width=True,
        )
        response_label_frame = kx.XScroll(view=self.response_label)
        with self.app.subtheme_context("secondary"):
            self.debug_label = kx.XLabel(
                font_name="RobotoMono-Regular",
                padding=(10, 10),
                halign="left",
                valign="top",
                fixed_width=True,
            )
            debug_label_frame = kx.frame(kx.XScroll(view=self.debug_label), bg=True)
        # Assemble
        debug_label_frame.set_size(hx=0.3)
        self.requests_frame.set_size(x="350sp")
        bottom_frame = kx.XBox()
        bottom_frame.add_widgets(
            debug_label_frame,
            response_label_frame,
            self.requests_frame,
        )
        main_frame = kx.XBox(orientation="vertical")
        main_frame.add_widgets(title, kx.pad(bottom_frame))
        self.add_widget(main_frame)

    def _refresh_requests(self):
        self._client.send(pgnet.Packet(pgnet.util.Request.HELP), self._on_help_response)

    def _on_help_response(self, response: pgnet.Response):
        main_stack = kx.XDynamicBox(orientation="vertical")
        for request, params in response.payload.items():
            panel_widgets = {
                name: kx.XInputPanelWidget(label=f"{name}:", widget=ptype)
                for name, ptype in params.items()
            }
            with self.app.subtheme_context("secondary"):
                panel = kx.XInputPanel(
                    panel_widgets,
                    reset_text="",
                    invoke_text=request,
                    fill_button=True,
                )
                panel.on_invoke = functools.partial(self._on_request_invoke, request)
                panel = panel
            with self.app.subtheme_context("accent"):
                text = request.removeprefix("__pgnet__.")
                text = text.replace("_", " ").capitalize()
                lbl = kx.XLabel(text=text, bold=True, font_size="18dp")
                lbl = kx.frame(lbl, bg=True, frame=False, pad=False)
                lbl.set_size(y=kx.DEFAULT_BUTTON_HEIGHT)
            sub_stack = kx.XDynamicBox(orientation="vertical")
            sub_stack.add_widgets(lbl, panel)
            subframe = kx.frame(
                sub_stack,
                dynamic=True,
                frame=False,
                margins="20dp",
            )
            main_stack.add_widgets(subframe)
        if self.custom_packet_frame.parent:
            self.custom_packet_frame.parent.remove_widget(self.custom_packet_frame)
        main_stack.add_widget(self.custom_packet_frame)
        scroll = kx.XScroll(view=main_stack)
        with self.app.subtheme_context("secondary"):
            self.requests_frame.content = kx.frame(scroll, bg=True)

    def _request_debug(self, *args):
        self._client.send(
            pgnet.Packet(pgnet.util.Request.DEBUG),
            self._response_callback,
        )

    def _on_request_invoke(self, request: str, values: dict):
        self._client.send(pgnet.Packet(request, values), self._response_callback)

    def _on_packet_input(self, w, values):
        message = values["message"]
        payload_text = values["payload"]
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = dict()
        packet = pgnet.Packet(message, payload)
        self._client.send(packet, self._response_callback)
        self.packet_input.set_focus("message")

    def _response_callback(self, response: pgnet.Response):
        sb = self.app.theme.secondary
        status = _STATUSES[response.status]
        status_color = sb.fg_warn if status else sb.fg
        statusstr = status_color.markup(status.name)
        timestr = arrow.get(response.created_on).to("local").format("HH:mm:ss MMM DD")
        debug_strs = [
            f"{sb.fg_accent.markup('Status:')} {status.value} ({statusstr})",
            f"{sb.fg_accent.markup('Created:')} {timestr}",
            response.debug_repr,
        ]
        self.debug_label.text = "\n\n".join(debug_strs)
        sb = self.app.theme.primary
        response_strs = [
            f"{sb.fg_accent.markup('Response:')} {response.message}",
        ]
        for k, v in response.payload.items():
            vstr = v if isinstance(v, str) else pprint.pformat(v, width=10_000)
            response_strs.append(f"\n[u]{sb.fg_accent.markup(k)}[/u]\n{vstr}")
        self.response_label.text = "\n".join(response_strs)

    def set_focus(self, *args):
        """Refresh requests frame on focus if empty."""
        if not self.requests_frame.content:
            self._refresh_requests()
