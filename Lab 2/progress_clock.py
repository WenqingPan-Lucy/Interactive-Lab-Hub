import time
from datetime import datetime, timedelta
import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789

cs_pin = digitalio.DigitalInOut(board.D5)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = None
BAUDRATE = 64000000
spi = board.SPI()
disp = st7789.ST7789(
    spi,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
    width=135,
    height=240,
    x_offset=53,
    y_offset=40,
)


height = disp.width
width = disp.height
image = Image.new(
    "RGB",
    (width, height)
)
rotation = 90
draw = ImageDraw.Draw(image)

title_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    21
)
percent_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    24
)
small_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    15
)

backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output(
    value=True
)


buttonA = digitalio.DigitalInOut(
    board.D23
)

# Bottom button
buttonB = digitalio.DigitalInOut(
    board.D24
)

buttonA.switch_to_input(
    pull=digitalio.Pull.UP
)

buttonB.switch_to_input(
    pull=digitalio.Pull.UP
)

SEMESTER_START = datetime(
    2026,
    8,
    24
)
SEMESTER_END = datetime(
    2026,
    12,
    20
)



current_screen = "TODAY"

previous_a = False
previous_b = False


def calculate_progress(start, end, now):

    total_seconds = (
        end - start
    ).total_seconds()

    passed_seconds = (
        now - start
    ).total_seconds()

    progress = (
        passed_seconds /
        total_seconds
    )

    progress = max(
        0,
        min(progress, 1)
    )

    remaining_seconds = max(
        0,
        (
            end - now
        ).total_seconds()
    )

    return progress, remaining_seconds


def draw_progress_screen(
    title,
    progress,
    remaining_seconds
):

    # Clear screen
    draw.rectangle(
        (
            0,
            0,
            width,
            height
        ),
        fill=(0, 0, 0)
    )


    title_box = draw.textbbox(
        (0, 0),
        title,
        font=title_font
    )

    title_width = (
        title_box[2]
        - title_box[0]
    )

    draw.text(
        (
            (width - title_width) // 2,
            7
        ),
        title,
        font=title_font,
        fill=(255, 255, 255)
    )


    percentage = progress * 100

    percentage_text = (
        f"{percentage:.1f}%"
    )

    percentage_box = draw.textbbox(
        (0, 0),
        percentage_text,
        font=percent_font
    )

    percentage_width = (
        percentage_box[2]
        - percentage_box[0]
    )

    draw.text(
        (
            (width - percentage_width) // 2,
            37
        ),
        percentage_text,
        font=percent_font,
        fill=(255, 255, 255)
    )


    bar_x = 20
    bar_y = 75

    bar_width = 200
    bar_height = 18


    # Background
    draw.rectangle(
        (
            bar_x,
            bar_y,
            bar_x + bar_width,
            bar_y + bar_height
        ),
        outline=(255, 255, 255),
        fill=(35, 35, 35)
    )


    # Amount filled
    filled_width = int(
        bar_width * progress
    )


    # Change color depending
    # on how much time has passed

    if progress < 0.5:

        bar_color = (
            80,
            200,
            120
        )

    elif progress < 0.8:

        bar_color = (
            255,
            200,
            80
        )

    else:

        bar_color = (
            255,
            100,
            100
        )


    draw.rectangle(
        (
            bar_x,
            bar_y,
            bar_x + filled_width,
            bar_y + bar_height
        ),
        fill=bar_color
    )

    remaining_days = int(
        remaining_seconds
        // 86400
    )

    remaining_hours = int(
        (
            remaining_seconds
            % 86400
        )
        // 3600
    )

    remaining_minutes = int(
        (
            remaining_seconds
            % 3600
        )
        // 60
    )


    if title == "TODAY":

        remaining_text = (
            f"{remaining_hours}h "
            f"{remaining_minutes}m left"
        )

    elif title == "THIS WEEK":

        remaining_text = (
            f"{remaining_days}d "
            f"{remaining_hours}h left"
        )

    else:

        remaining_text = (
            f"{remaining_days} days left"
        )


    remaining_box = draw.textbbox(
        (0, 0),
        remaining_text,
        font=small_font
    )

    remaining_width = (
        remaining_box[2]
        - remaining_box[0]
    )


    draw.text(
        (
            (width - remaining_width) // 2,
            104
        ),
        remaining_text,
        font=small_font,
        fill=(200, 200, 200)
    )


    # Push image to display
    disp.image(
        image,
        rotation
    )


while True:

    # Buttons are active LOW
    a_pressed = (
        buttonA.value == False
    )

    b_pressed = (
        buttonB.value == False
    )

    # Both buttons return to TODAY
    if (
        a_pressed
        and b_pressed
        and not (
            previous_a
            and previous_b
        )
    ):

        current_screen = "TODAY"


    # Top button → THIS WEEK
    elif (
        a_pressed
        and not previous_a
    ):

        current_screen = "WEEK"


    # Bottom button → SEMESTER
    elif (
        b_pressed
        and not previous_b
    ):

        current_screen = "SEMESTER"


    previous_a = a_pressed
    previous_b = b_pressed


    now = datetime.now()


    if current_screen == "TODAY":

        start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        end = (
            start
            + timedelta(days=1)
        )

        progress, remaining = (
            calculate_progress(
                start,
                end,
                now
            )
        )

        draw_progress_screen(
            "TODAY",
            progress,
            remaining
        )


    elif current_screen == "WEEK":

        # Monday at 00:00
        start = (
            now
            - timedelta(
                days=now.weekday()
            )
        )

        start = start.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        # Next Monday
        end = (
            start
            + timedelta(days=7)
        )

        progress, remaining = (
            calculate_progress(
                start,
                end,
                now
            )
        )

        draw_progress_screen(
            "THIS WEEK",
            progress,
            remaining
        )



    elif current_screen == "SEMESTER":

        progress, remaining = (
            calculate_progress(
                SEMESTER_START,
                SEMESTER_END,
                now
            )
        )

        draw_progress_screen(
            "SEMESTER",
            progress,
            remaining
        )


    time.sleep(0.1)