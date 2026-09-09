import html
from typing import Any

from pyrogram.enums import ParseMode
from yt_shared.schemas.playlist import PlaylistInfoPayload

from bot.core.handlers.abstract import AbstractDownloadHandler
from bot.core.utils import bold


class PlaylistInfoHandler(AbstractDownloadHandler):
    """Notify the user that a playlist/series link was expanded into single videos."""

    _body: PlaylistInfoPayload

    _MSG_TPL = '📺 {title}\n🔢 {queued}\n⏳ {footer}'

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
        title = html.escape(self._body.title or self._body.url)
        queued_count = self._body.queued_count
        total_count = self._body.total_count

        queued = f'{queued_count} video{"s" if queued_count != 1 else ""} queued'
        if total_count > queued_count:
            queued = f'{queued} out of {total_count} (limit reached)'

        return self._MSG_TPL.format(
            title=bold(title),
            queued=bold(queued),
            footer='Each video is downloaded as a separate task.',
        )
