from pilucca.conf import settings

from pilucca import ILuccaClient
from pilucca.models import UpdatedResult
from pilucca.utils import create_intervals, send_telegram_notification, group_absence_dates

from logging import getLogger

logger = getLogger("pilucca")


if __name__ == '__main__':
    logger.info("Starting")
    if settings.DEBUG:
        logger.info(f'Working in DEBUG Mode! 🥷')
        logger.info(f'SETTINGS:')
        logger.info(f'\tDEBUG: {settings.DEBUG}')
        logger.info(f'\tILUCCA_USERNAME: {settings.ILUCCA_USERNAME}')
        logger.info(f'\tILUCCA_PASSWORD: {settings.ILUCCA_PASSWORD[:2]}******{settings.ILUCCA_PASSWORD[-2:]}')
        logger.info(f'\tTELEGRAM_TOKEN: {settings.TELEGRAM_TOKEN[:3]}***********{settings.TELEGRAM_TOKEN[-3:]}')
        logger.info(f'\tTELEGRAM_CHAT_ID: {settings.TELEGRAM_CHAT_ID[:3]}****{settings.TELEGRAM_CHAT_ID[-3:]}')


    pl = ILuccaClient()
    try:
        pl.login()
        me = pl.principal()

        owlai = pl.office_work_location_authorized_interval()
        logger.info(f'Authorized interal from {owlai.authorizedInputInterval.start} to {owlai.authorizedInputInterval.end}')

        intervals = create_intervals(owlai.authorizedInputInterval.start, owlai.authorizedInputInterval.end)

        logger.info(f'Intervals to work:')
        for start, end in intervals:
            logger.info(f'  {start} to {end}')

        updates = []
        absences = []

        for start, end in intervals:
            data = pl.office_work_location_timeline(me.id, start, end)

            total_office = 0
            total_teleworking = 0
            not_entered_days = 0
            not_working_days = 0

            for pos, day in data.root.items() :  # DayEntry
                if day.fullDay.name == "day not entered":
                    not_entered_days += 1
                elif day.fullDay.name == "day not worked":
                    not_working_days += 1
                elif day.fullDay.name == "Teleworking":
                    total_teleworking += 1
                elif day.fullDay.name == "Absence":
                    absences.append(day.date)
                elif day.fullDay.name.endswith("Office"):
                    total_office += 1

            if not_entered_days == 0:
                continue

            logger.info(f'⛏️ Need to force week for {start} to {end}')
            if settings.DEBUG:
                updated = UpdatedResult(
                    success=True,
                    start_date=start,
                    end_date=end,
                )
            else:
                res = pl.office_work_location_from_week_template(start)
                updated = UpdatedResult(
                    success=res.saved,
                    start_date=start,
                    end_date=end,
                )
                logger.info(f'\t✅Saved default: {res.saved}. warnings: {res.warnings}, overbookings: {res.overbookings}, exceeded_rules: {res.exceededRules}')

            updates.append(updated)

        if settings.TELEGRAM_ENABLED:
            logger.info(f'Sending Telegram Notification')

            user = f'(<i>{me.id})</i> {me.first_name} {me.last_name}'
            # 1. Generate the date list as a string
            # Assumes 'modified_days' is a list of strings like ["2026-02-09", "2026-02-10"]
            dates_list_html = "".join(
                [f"  • 📅 <code>{update.start_date}</code> to <code>{update.end_date}</code>\n" for update in updates])


            # 2. Construct the HTML Message
            message = (
                f"<b>🚀 Lucca Application Update</b>\n\n"
                f"<b>User:</b> {user}\n"
                f"<b>Status:</b> Modified dates for this week:\n"
                f"{dates_list_html}\n"
            )

            # 3. Generate absence days
            if len(absences) > 0:
                abs_groups = group_absence_dates(absences)

                absences_list_html = ""
                for group in abs_groups:
                    if group.get('end'):
                        absences_list_html += f"  • 🌴 <code>{group['start']}</code> to <code>{group['end']}</code>\n"
                    else:
                        absences_list_html += f"  • 🌴 <code>{group['start']}</code>\n"

                message += f"<b>Absences:</b>\n{absences_list_html}\n"



            send_telegram_notification(message=message, mode='HTML')

    finally:
        pl.write_har_file()
