from typing import TypedDict

from telebot import types as tg
from telebot_components.form.field import BadFieldValueError, FormField
from telebot_components.form.form import Form, FormBranch
from telebot_components.form.handler import FormHandler


class VideoNoteField(FormField[tg.VideoNote]):
    def parse(self, message: tg.Message) -> tg.VideoNote:
        circle = message.video_note
        if not circle:
            raise BadFieldValueError("video note (circle) expected!")
        return circle


single_video_note_form = Form(
    fields=[
        VideoNoteField(
            name="video_note",
            required=True,
            query_message="send a video note (circle)...",
        ),
    ],
)


class SingleVideoNoteFieldResult(TypedDict):
    video_note: tg.VideoNote
