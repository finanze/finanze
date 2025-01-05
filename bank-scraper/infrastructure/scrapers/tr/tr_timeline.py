import logging
from datetime import datetime
from typing import Optional

from pytr.api import TradeRepublicError
from pytr.utils import preview


class TRTimeline:
    TIMELINE_DATA_TYPES = [
        "timelineTransactions",
        "timelineActivityLog",
        "timelineDetailV2",
    ]

    def __init__(self,
                 tr,
                 since: Optional[datetime] = None,
                 already_registered_ids: set[str] = None,
                 requested_data: list = TIMELINE_DATA_TYPES):
        self.tr = tr
        self.since = since
        self.requested_data = requested_data

        self.log = logging.getLogger(__name__)

        self.received_detail = 0
        self.requested_detail = 0
        self.events = []
        self.events = []

        self.num_timelines = 0
        self.timeline_events = {}

        self.already_registered_ids = already_registered_ids if already_registered_ids else set()

    async def fetch(self):
        if not self.requested_data or self.requested_data == ["timelineDetailV2"]:
            return []

        if "timelineTransactions" in self.requested_data:
            await self._request_timeline_transactions()

        if "timelineActivityLog" in self.requested_data:
            await self._request_timeline_activity_log()

        while True:
            try:
                _, subscription, response = await self.tr.recv()
            except TradeRepublicError as e:
                self.log.error(
                    f'Error response for subscription "{e.subscription}". Re-subscribing...'
                )
                await self.tr.subscribe(e.subscription)
                continue

            if "timelineTransactions" in self.requested_data and subscription.get("type", "") == "timelineTransactions":
                await self._process_and_request_next_timeline_transactions(response)

            elif "timelineActivityLog" in self.requested_data and subscription.get("type", "") == "timelineActivityLog":
                await self._process_and_request_next_timeline_activity_log(response)

            elif "timelineDetailV2" in self.requested_data and subscription.get("type", "") == "timelineDetailV2":
                result = await self.process_timeline_detail(response)
                if result:
                    return result
            else:
                self.log.warning(
                    f"unmatched subscription of type '{subscription['type']}':\n{preview(response)}"
                )

    async def _request_timeline_transactions(self):
        self.log.info("Subscribing to #1 timeline transactions")
        self.num_timelines = 0
        await self.tr.timeline_transactions()

    async def _request_timeline_activity_log(self):
        self.log.info("Awaiting #1  timeline activity log")
        self.num_timelines = 0
        await self.tr.timeline_activity_log()

    async def _process_and_request_next_timeline_transactions(self, response):
        """
        Get timelines transactions and save time in list timelines.
        Extract timeline transactions events and save them in list timeline_events
        """
        self.num_timelines += 1
        added_last_event = True
        for event in response["items"]:
            event_id = event["id"]
            if (
                    event_id not in self.already_registered_ids
                    and ((not self.since) or datetime.fromisoformat(event["timestamp"][:19]) >= self.since)
            ):
                event["source"] = "timelineTransaction"
                self.timeline_events[event_id] = event
            else:
                added_last_event = False
                break

        self.log.info(f"Received #{self.num_timelines:<2} timeline transactions")
        after = response["cursors"].get("after")
        if (after is not None) and added_last_event:
            self.log.info(
                f"Subscribing #{self.num_timelines + 1:<2} timeline transactions"
            )
            await self.tr.timeline_transactions(after)
        else:
            # last timeline is reached
            self.log.info("Received last relevant timeline transaction")
            if "timelineActivityLog" in self.requested_data:
                await self._request_timeline_activity_log()
            else:
                await self._request_all_timeline_details()

    async def _process_and_request_next_timeline_activity_log(self, response):
        """
        Get timelines activity log and save time in list timelines.
        Extract timeline activity log events and save them in list timeline_events
        """
        self.num_timelines += 1
        added_last_event = False
        for event in response["items"]:
            event_id = event["id"]
            if (
                    event_id not in self.already_registered_ids
                    and ((not self.since) or datetime.fromisoformat(event["timestamp"][:19]) >= self.since)
            ):
                if event_id in self.timeline_events:
                    self.log.warning(f"Received duplicate event {event_id}")
                else:
                    added_last_event = True
                event["source"] = "timelineActivity"
                self.timeline_events[event_id] = event
            else:
                break

        self.log.info(f"Received #{self.num_timelines:<2} timeline activity log")
        after = response["cursors"].get("after")
        if (after is not None) and added_last_event:
            self.log.info(
                f"Subscribing #{self.num_timelines + 1:<2} timeline activity log"
            )
            await self.tr.timeline_activity_log(after)
        else:
            self.log.info("Received last relevant timeline activity log")
            await self._request_all_timeline_details()

    async def _request_all_timeline_details(self):
        for event in self.timeline_events.values():
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
                self.log.debug(f"{msg} {event['title']}: {event.get('body')} ")
            else:
                self.requested_detail += 1
                await self.tr.timeline_detail_v2(event["id"])

        self.log.info("All timeline details requested")

    async def process_timeline_detail(self, response):
        self.received_detail += 1
        if response["id"] not in self.timeline_events:
            self.log.warning(f"Received unexpected detail {response['id']}")
            self.log.debug(f"{response}")
            return

        event = self.timeline_events[response["id"]]
        event["details"] = response

        max_details_digits = len(str(self.requested_detail))
        self.log.debug(
            f"{self.received_detail:>{max_details_digits}}/{self.requested_detail}: "
            + f"{event['title']} -- {event['subtitle']} - {event['timestamp'][:19]}"
        )

        self.events.append(event)

        if self.received_detail == self.requested_detail:
            self.log.info("Received all details")
            return self.events
