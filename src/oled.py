import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
import time


# Initialize the OLED display
def init_oled():
    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
    oled.fill(0)  # Clear the display
    oled.show()
    return oled


# Display a message on the OLED
def display_message(disp, message):
    width = disp.width
    height = disp.height
    image = Image.new("1", (width, height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)

    # Clear the screen
    draw.rectangle((0, 0, width, height), outline=0, fill=0)

    # Add text
    draw.text((0, 0), message, font=font, fill=255)

    # Display the image
    disp.image(image)
    disp.show()

def main():
    # Initialize the OLED display
    disp = init_oled()

    # Display "Working" message
    display_message(disp, "Working...")

    # Simulate some work
    time.sleep(5)  # Replace with actual work logic

    # Display "Completed" message
    display_message(disp, "Completed!")

    # Keep the message on screen for a while
    time.sleep(5)

    disp.fill(0)  # Clear the display
    disp.show()

if __name__ == "__main__":
    main()