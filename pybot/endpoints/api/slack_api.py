import logging

from sirbot import SirBot
from slack import ROOT_URL
from slack.exceptions import SlackAPIError

from pybot.endpoints.api.utils import (
    _slack_info_from_email,
    handle_slack_invite_error,
    production_only,
)

from pybot.endpoints.slack.utils.event_utils import (
    base_user_message,
    send_user_greetings,
)

from pybot.endpoints.slack.utils.event_messages import (
    identify_military_spouse,
    identify_military_ad,
)

from pybot.plugins import APIPlugin
from pybot.plugins.api.request import SlackApiRequest

logger = logging.getLogger(__name__)


def create_endpoints(plugin: APIPlugin):
    plugin.on_get("verify", verify, wait=True)
    plugin.on_get("invite", invite, wait=True)
    plugin.on_get("update", update, wait=True)


async def verify(request: SlackApiRequest, app: SirBot) -> dict:
    """
    Verifies whether a user exists in the configured slack group with
    the given email

    :return: The user's slack id and displayName if they exist
    """
    slack = app.plugins["slack"].api
    email = request.query["email"]

    user = await _slack_info_from_email(email, slack)
    if user:
        return {"exists": True, "id": user["id"], "displayName": user["name"]}
    return {"exists": False}


async def update(request: SlackApiRequest, app: SirBot) -> dict:
    """
    Verifies whether a user exists in the configured slack group with
    the given email

    :return: The user's slack id and displayName if they exist
    """
    slack = app.plugins["slack"].api
    slack_id = request.query["slack_id"]
    military_status = request.query["military_status"]
    if military_status not in ('current', 'spouse'):
        return
    user_message = base_user_message(slack_id)

    if military_status == 'current':
        user_message['text'] = identify_military_ad(slack_id)
    elif military_status == 'spouse':
        user_message['text'] = identify_military_spouse(slack_id)

    send_user_greetings([user_message], slack)

    return {"success": "true"}



@production_only
async def invite(request: SlackApiRequest, app: SirBot):
    """
    Pulls an email out of the querystring and sends it an invite
    to the slack team

    :return: The request response from slack
    """

    admin_slack = app.plugins["admin_slack"].api
    slack = app.plugins["slack"].api
    body = await request.json()

    if "email" not in body:
        return {"error": "Must contain `email` JSON value"}
    email = body["email"]

    try:
        response = await admin_slack.query(
            url=ROOT_URL + "users.admin.invite", data={"email": email}
        )
        return response

    except SlackAPIError as e:
        logger.info("Slack invite resulted in SlackAPIError: " + e.error)
        await handle_slack_invite_error(email, e, slack)
        return e.data

    except Exception as e:
        logger.exception(e)
        await handle_slack_invite_error(email, e, slack)
        return e
