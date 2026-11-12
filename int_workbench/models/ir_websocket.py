import re

from odoo import models

# What the page asks for: the bus channel of one controller ("int.workbench.device_17"), like "discuss.channel_17" of Discuss.
DEVICE_CHANNEL = re.compile(r"int\.workbench\.device_(\d+)")


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        """A page may listen to the controllers it may read, and to no others: the name it sends is turned into the record by a search
        with the rights of the user, so a controller that the user cannot read is not subscribed."""
        channels = list(channels)  # do not alter the original list
        ids = []
        for channel in list(channels):
            match = isinstance(channel, str) and DEVICE_CHANNEL.fullmatch(channel)
            if match:
                channels.remove(channel)
                ids.append(int(match.group(1)))
        if ids and self.env["int.workbench.device"].has_access("read"):
            channels.extend(self.env["int.workbench.device"].search([("id", "in", ids)]))
        return super()._build_bus_channel_list(channels)
