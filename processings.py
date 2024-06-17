import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

import ffmpeg  # type: ignore
import imageio.v3 as iio
import numpy as np
from telebot import AsyncTeleBot
from telebot import types as tg


@dataclass
class VideoProcessingContext:
    video: bytes
    bot: AsyncTeleBot
    user: tg.User


VideoProcessing = Callable[[VideoProcessingContext], Awaitable[None]]


def make_frames_to_image_processing(frames_processor: Callable[[np.ndarray], np.ndarray]) -> VideoProcessing:
    async def proc(ctx: VideoProcessingContext) -> None:
        frames = iio.imread(ctx.video, plugin="pyav")
        avg_frame = frames_processor(frames)
        avg_frame = avg_frame.astype(frames.dtype)
        image_body = iio.imwrite("<bytes>", image=avg_frame, extension=".png")
        await ctx.bot.send_photo(
            chat_id=ctx.user.id,
            photo=image_body,
        )

    return proc


average = make_frames_to_image_processing(lambda frames: np.mean(frames, axis=0))
median = make_frames_to_image_processing(lambda frames: np.median(frames, axis=0))


async def datamosh_basic(ctx: VideoProcessingContext):
    with tempfile.TemporaryDirectory(prefix="media-processor-bot") as tempdir_path:
        tempdir = Path(tempdir_path)
        input_temp = tempdir / "input.mp4"
        input_temp.write_bytes(ctx.video)

        input_avi_bytes: bytes
        input_avi_bytes, _ = (
            ffmpeg.input(input_temp).output("pipe:", format="avi").run(capture_stdout=True, capture_stderr=True)
        )

        output_avi_filename = tempdir / "temp_moshed.avi"
        AVI_ENDFRAME = bytes.fromhex("30306463")
        with open(output_avi_filename, "wb") as out_f:
            frames = input_avi_bytes.split(AVI_ENDFRAME)
            iframe_header = bytes.fromhex("0001B0")
            iframe_written = False
            for _, frame in enumerate(frames):
                if not iframe_written:
                    out_f.write(frame + AVI_ENDFRAME)
                    if frame[5:8] == iframe_header:
                        iframe_written = True
                else:
                    # while we're moshing we're repeating p-frames and multiplying i-frames
                    if frame[5:8] != iframe_header:
                        # for i in range(repeat_p_frames):
                        out_f.write(frame + bytes.fromhex("30306463"))

        output_mp4_filename = tempdir / "output.mp4"
        ffmpeg.input(str(output_avi_filename.absolute())).output(str(output_mp4_filename.absolute())).run(
            capture_stderr=True
        )

        await ctx.bot.send_video_note(
            chat_id=ctx.user.id,
            data=output_mp4_filename.read_bytes(),
        )


if __name__ == "__main__":
    video = Path("temp.mp4").read_bytes()
    asyncio.run(
        datamosh_basic(
            VideoProcessingContext(
                video,
                None,  # type: ignore
                None,  # type: ignore
            )
        )
    )
