from app.client import WaterStreamClient


def main() -> None:
    client = WaterStreamClient()

    try:
        client.run()

    except KeyboardInterrupt:
        print("\nApplication stopped by user.")

    except ConnectionRefusedError:
        print("\nCould not connect to stream server.")
        print(
            "Make sure water_ai_stream_server.py "
            "is running on localhost:9034."
        )

    except OSError as exc:
        print(f"\nSocket error: {exc}")

    except Exception as exc:
        print(f"\nUnexpected error: {exc}")


if __name__ == "__main__":
    main()