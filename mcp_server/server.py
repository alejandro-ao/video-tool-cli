from tools.video_tools import mcp
from dotenv import load_dotenv

load_dotenv()


if __name__ == "__main__":
    mcp.run(transport="stdio")