import html
from typing import Any

from pyrogram.enums import ParseMode
from yt_shared.schemas.playlist import PlaylistInfoPayload

from bot.core.handlers.abstract import AbstractDownloadHandler
from bot.core.utils import bold


class PlaylistInfoHandler(AbstractDownloadHandler):
    """Notify the user that a playlist/series link was expanded into single videos."""

    _body: PlaylistInfoPayload

    _FOOTER = 'Each video is downloaded as a separate task.'
    _NOTHING_TO_DO_FOOTER = 'Nothing to download.'

    async def handle(self) -> None:
        await self._delete_acknowledgment_message()
        await self._send_playlist_info()

    async def _send_playlist_info(self) -> None:
        text = self._format_playlist_info()
        for user in self._receiving_users:
            kwargs: dict[str, Any] = {
                'chat_id': user.id,
                'text': text,
                'parse_mode': ParseMode.HTML,
            }
            if self._body.message_id:
                kwargs['reply_to_message_id'] = self._body.message_id
            await self._bot.send_message(**kwargs)

    def _format_playlist_info(self) -> str:
        queued_count = self._body.queued_count
        skipped_count = self._body.skipped_count
        total_count = self._body.total_count

        lines = [f'📺 {bold(html.escape(self._body.title or self._body.url))}']

        found = f'{total_count} video{"s" if total_count != 1 else ""} found'
        truncated = total_count > queued_count + skipped_count
        if truncated:
            found = f'{found}, limited to {queued_count + skipped_count}'
        lines.append(f'🔢 {bold(found)}')

        if skipped_count:
            lines.append(f'⏭️ {bold(f"{skipped_count} already downloaded")}, skipped')

        lines.append(f'⬇️ {bold(f"{queued_count} queued")}')
        lines.append(
            f'⏳ {self._FOOTER if queued_count else self._NOTHING_TO_DO_FOOTER}'
        )
        return '\n'.join(lines)
