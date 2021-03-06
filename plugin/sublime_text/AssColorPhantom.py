import sublime
import sublime_plugin
from ..functions import (
    find_color_regions_by_region,
    hex_to_rgba,
    is_my_syntax,
    view_typing_timestamp_val,
    view_update_color_regions,
    view_color_regions_val,
)
from ..Globals import Globals
from ..settings import get_package_name, get_setting, get_timestamp

PHANTOM_TEMPLATE = """
    <body id="ass-color-box">
        <style>
            div.phantom-box {{
                border: 1px solid var(--foreground);
            }}
            div.half-box {{
                padding: 0.2em 0.4em;
            }}
            div.opaque-box {{
                background-color: rgba({r}, {g}, {b}, 1);
            }}
            div.alpha-box {{
                background-color: rgba({r}, {g}, {b}, {a});
            }}
        </style>
        <div class="phantom-box">
            <div class="half-box opaque-box"></div>
            <div class="half-box alpha-box"></div>
        </div>
    </body>
"""


class AssColorPhantom(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        self.view = view
        self.phantom_set = sublime.PhantomSet(self.view, get_package_name())
        view_typing_timestamp_val(self.view, 0)
        view_color_regions_val(self.view, [])

    def __del__(self) -> None:
        self._erase_phantom()

    def on_load_async(self) -> None:
        if not self._is_this_listener_activated():
            return

        self._detect_colors()

    def on_activated_async(self) -> None:
        if not self._is_this_listener_activated():
            return

        self._detect_colors()

    def on_modified_async(self) -> None:
        if not self._is_this_listener_activated():
            return

        view_typing_timestamp_val(self.view, get_timestamp())

        # fmt: off
        sublime.set_timeout_async(
            self.on_modified_async_callback,
            get_setting("on_modified_typing_period"),
        )
        # fmt: on

    def on_modified_async_callback(self) -> None:
        now_s = get_timestamp()
        pass_ms = (now_s - view_typing_timestamp_val(self.view)) * 1000

        if pass_ms >= get_setting("on_modified_typing_period"):
            view_typing_timestamp_val(self.view, now_s)
            self._detect_colors()

    def on_hover(self, point: int, hover_zone: int) -> None:
        if not self._is_this_listener_activated():
            return

        if get_setting("show_color_phantom") == "hover":
            self._update_phantom(find_color_regions_by_region(self.view, point))

    def _is_this_listener_activated(self):
        return is_my_syntax(self.view) and get_setting("show_color_phantom") != "never"

    def _detect_colors(self) -> None:
        color_regions = view_update_color_regions(self.view, Globals.color_scope)

        if get_setting("show_color_phantom") == "always":
            self._update_phantom(color_regions)

    def _generate_phantom_html(self, color: str) -> str:
        match = Globals.color_abgr_regex_obj.match(color)

        if not match:
            return "?"

        # fmt: off
        return PHANTOM_TEMPLATE.format(**hex_to_rgba(
            "".join(match.group("r", "g", "b")),
            # opaque if alpha is not specified
            match.group("a") or "00",
        ))
        # fmt: on

    def _new_color_phantom(self, color_region) -> sublime.Phantom:
        # always make "color_region" a sublime.Region object
        if not isinstance(color_region, sublime.Region):
            color_region = sublime.Region(*(color_region[0:2]))

        # Calculate the point to insert the phantom.
        #
        # Usually it's exact at the end of color, but if the next char is a quotation mark,
        # there could be a problem on break "scope brackets" highlighting in BracketHilighter.
        # In that case, we shift the position until the next char is not a quotation mark.
        phantom_point = color_region.end()
        while self.view.substr(phantom_point) in "'\"":
            phantom_point += 1

        return sublime.Phantom(
            sublime.Region(phantom_point),
            self._generate_phantom_html(self.view.substr(color_region)),
            sublime.LAYOUT_INLINE,
        )

    def _new_color_phantoms(self, color_regions: list) -> list:
        return [self._new_color_phantom(r) for r in color_regions]

    def _erase_phantom(self) -> None:
        self.phantom_set.update([])

    def _update_phantom(self, color_regions: list) -> None:
        self.phantom_set.update(self._new_color_phantoms(color_regions))
