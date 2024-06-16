import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

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


if __name__ == "__main__":
    video = Path("temp.mp4").read_bytes()
    asyncio.run(
        average(
            VideoProcessingContext(
                video,
                None,  # type: ignore
                None,  # type: ignore
            )
        )
    )
