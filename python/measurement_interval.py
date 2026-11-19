from dataclasses import dataclass


@dataclass(frozen=True)
class MeasurementFrameRange:
    start_frame: int
    end_frame: int
    total_video_frames: int

    def __post_init__(self):
        values = (self.start_frame, self.end_frame, self.total_video_frames)
        if any(type(value) is not int for value in values):
            raise ValueError("Measurement frame numbers must be integers.")
        if self.total_video_frames < 1:
            raise ValueError("The video must contain at least one frame.")
        if (
            self.start_frame < 1
            or self.end_frame < self.start_frame
            or self.end_frame > self.total_video_frames
        ):
            raise ValueError(
                "Measurement frames must be an inclusive range within the video."
            )

    @property
    def frame_count(self) -> int:
        return self.end_frame - self.start_frame + 1

    def includes(self, frame_number: int) -> bool:
        return self.start_frame <= frame_number <= self.end_frame
