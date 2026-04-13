import argparse
import threading
import time

from automation.main import start_automation
from data_processing.main import start_data_processing
from model_training.train import start_training


def run_all():
    """同时启动 automation 和 data_processing"""
    t1 = threading.Thread(target=start_automation, daemon=True)
    t2 = threading.Thread(target=start_data_processing, daemon=True)

    t1.start()
    t2.start()

    print("[INFO] automation + data_processing 已启动")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] 系统已停止")


def main():
    parser = argparse.ArgumentParser(description="WoW Auction AI System Launcher")
    parser.add_argument(
        "--mode",
        choices=["automation", "process", "train", "all"],
        default="all",
        help="选择启动模式"
    )
    args = parser.parse_args()

    if args.mode == "automation":
        start_automation()
    elif args.mode == "process":
        start_data_processing()
    elif args.mode == "train":
        start_training()
    elif args.mode == "all":
        run_all()


if __name__ == "__main__":
    main()