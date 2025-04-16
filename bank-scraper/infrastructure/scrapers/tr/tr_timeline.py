# MIT License

# Copyright (c) 2020 nborrmann

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import logging
from datetime import datetime
from typing import Optional

from pytr.api import TradeRepublicError, TradeRepublicApi
from pytr.utils import preview


class TRTimeline:
    TIMELINE_DATA_TYPES = [
        "timelineTransactions",
        "timelineActivityLog",
        "timelineDetailV2",
    ]

    def __init__(self,
                 tr: TradeRepublicApi,
                 since: Optional[datetime] = None,
                 already_registered_ids: set[str] = None,
                 requested_data: list = TIMELINE_DATA_TYPES):
        self._tr = tr
        self._since = since
        self._already_registered_ids = already_registered_ids if already_registered_ids else set()
        self._requested_data = requested_data

        self._log = logging.getLogger(__name__)

        self._received_detail = 0
        self._requested_detail = 0

        self._num_timelines = 0
        self._timeline_events = {}

        self.events = []

    async def fetch(self):
        if not self._requested_data or self._requested_data == ["timelineDetailV2"]:
            return []

        if "timelineTransactions" in self._requested_data:
            await self._request_timeline_transactions()

        if "timelineActivityLog" in self._requested_data:
            await self._request_timeline_activity_log()

        while True:
            try:
                _, subscription, response = await self._tr.recv()
            except TradeRepublicError as e:
                self._log.error(
                    f'Error response for subscription "{e.subscription}". Re-subscribing...'
                )
                await self._tr.subscribe(e.subscription)
                continue

            if "timelineTransactions" in self._requested_data and subscription.get("type",
                                                                                   "") == "timelineTransactions":
                result = await self._process_and_request_next_timeline_transactions(response)
                if result is not None:
                    return result

            elif "timelineActivityLog" in self._requested_data and subscription.get("type",
                                                                                    "") == "timelineActivityLog":
                await self._process_and_request_next_timeline_activity_log(response)

            elif "timelineDetailV2" in self._requested_data and subscription.get("type", "") == "timelineDetailV2":
                result = await self._process_timeline_detail(response)
                if result:
                    return result
            else:
                self._log.warning(
                    f"unmatched subscription of type '{subscription['type']}':\n{preview(response)}"
                )

    async def _request_timeline_transactions(self):
        self._log.info("Subscribing to #1 timeline transactions")
        self._num_timelines = 0
        await self._tr.timeline_transactions()

    async def _request_timeline_activity_log(self):
        self._log.info("Awaiting #1  timeline activity log")
        self._num_timelines = 0
        await self._tr.timeline_activity_log()

    async def _process_and_request_next_timeline_transactions(self, response):
        """
        Get timelines transactions and save time in list timelines.
        Extract timeline transactions events and save them in list timeline_events
        """
        self._num_timelines += 1
        added_last_event = True
        for event in response["items"]:
            event_id = event["id"]
            if (
                    event_id not in self._already_registered_ids
                    and ((not self._since) or datetime.fromisoformat(event["timestamp"][:19]) >= self._since)
            ):
                event["source"] = "timelineTransaction"
                self._timeline_events[event_id] = event
            else:
                added_last_event = False
                break

        self._log.info(f"Received #{self._num_timelines:<2} timeline transactions")
        after = response["cursors"].get("after")
        if (after is not None) and added_last_event:
            self._log.info(
                f"Subscribing #{self._num_timelines + 1:<2} timeline transactions"
            )
            await self._tr.timeline_transactions(after)
        else:
            # last timeline is reached
            self._log.info("Received last relevant timeline transaction")
            if "timelineActivityLog" in self._requested_data:
                await self._request_timeline_activity_log()
            else:
                if self._timeline_events:
                    await self._request_all_timeline_details()
                else:
                    return []
        return None

    async def _process_and_request_next_timeline_activity_log(self, response):
        """
        Get timelines activity log and save time in list timelines.
        Extract timeline activity log events and save them in list timeline_events
        """
        self._num_timelines += 1
        added_last_event = False
        for event in response["items"]:
            event_id = event["id"]
            if (
                    event_id not in self._already_registered_ids
                    and ((not self._since) or datetime.fromisoformat(event["timestamp"][:19]) >= self._since)
            ):
                if event_id in self._timeline_events:
                    self._log.warning(f"Received duplicate event {event_id}")
                else:
                    added_last_event = True
                event["source"] = "timelineActivity"
                self._timeline_events[event_id] = event
            else:
                break

        self._log.info(f"Received #{self._num_timelines:<2} timeline activity log")
        after = response["cursors"].get("after")
        if (after is not None) and added_last_event:
            self._log.info(
                f"Subscribing #{self._num_timelines + 1:<2} timeline activity log"
            )
            await self._tr.timeline_activity_log(after)
        else:
            self._log.info("Received last relevant timeline activity log")
            await self._request_all_timeline_details()

    async def _request_all_timeline_details(self):
        for event in self._timeline_events.values():
            action = event.get("action")
            msg = ""
            if action is None:
                if event.get("actionLabel") is None:
                    msg += "Skip: no action"

            elif action.get("type") != "timelineDetail":
                msg += f"Skip: action type unmatched ({action['type']})"

            elif action.get("payload") != event["id"]:
                msg += f"Skip: payload unmatched ({action['payload']})"

            if msg != "":
                self.events.append(event)
                self._log.debug(f"{msg} {event['title']}: {event.get('body')} ")
            else:
                self._requested_detail += 1
                await self._tr.timeline_detail_v2(event["id"])

        self._log.info("All timeline details requested")

    async def _process_timeline_detail(self, response):
        self._received_detail += 1
        if response["id"] not in self._timeline_events:
            self._log.warning(f"Received unexpected detail {response['id']}")
            self._log.debug(f"{response}")
            return

        event = self._timeline_events[response["id"]]
        event["details"] = response

        max_details_digits = len(str(self._requested_detail))
        self._log.debug(
            f"{self._received_detail:>{max_details_digits}}/{self._requested_detail}: "
            + f"{event['title']} -- {event['subtitle']} - {event['timestamp'][:19]}"
        )

        self.events.append(event)

        if self._received_detail == self._requested_detail:
            self._log.info("Received all details")
            return self.events
