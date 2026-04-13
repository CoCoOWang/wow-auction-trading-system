# magic_wow_automation/vm_control.py
import subprocess
import time
import psutil
import os
from utils.log import logger
from utils.config_loader import config
from task_executor.image_detection import detect_target

VMX_PATHS = config["vmx_paths"]
VM_TITLES = config["vm_titles"]
NUM_VMS_TO_START = config.get("num_vms_to_start", 2)
VMRUN_PATH = config["vmrun_path"]
TAG_ICON_CLASS_NAME = "TAG-LINK-ICON"
VM_BOOT_WAIT = config.get("vm_boot_wait", 20)


def is_vm_running(title):
    """
    判断某个 VM 窗口是否已存在（以标题判断）
    """
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if "vmware-vmx" in proc.info['name'].lower():
                for arg in proc.info.get("cmdline", []):
                    if title.lower() in arg.lower():
                        return True
        except Exception:
            continue
    return False


def start_vm(index):
    """
    启动指定索引的虚拟机（使用 VMware 的 vmrun 工具）
    """
    if not os.path.exists(VMRUN_PATH):
        logger.error(f"[VM] vmrun.exe 路径无效: {VMRUN_PATH}")
        return False
    vmx = VMX_PATHS[index]
    title = VM_TITLES[index]

    if is_vm_running(title):
        logger.info(f"[VM] {title} 已在运行，跳过启动")
        return True

    for attempt in range(3):
        try:
            logger.info(vmx)
            subprocess.run([VMRUN_PATH, "start", vmx], check=True)
            logger.info(f"[VM] 启动 VM{index+1} 成功: {vmx}")
            return True
        except Exception as e:
            logger.warning(f"[VM] 启动 VM{index+1} 第 {attempt+1} 次失败: {e}")
            time.sleep(5)
    logger.error(f"[VM] 启动 VM{index+1} 失败，已重试3次")
    return False


def wait_for_tag_icon(max_wait=180):
    """等待检测到 TAG 图标"""
    for _ in range(max_wait // 5):
        found, _ = detect_target(TAG_ICON_CLASS_NAME)
        if found:
            logger.info("[VM] 已识别到 TAG 图标，允许继续启动下一个虚拟机")
            return True
        logger.info("[等待] 尚未识别到 TAG 图标，继续等待...")
        time.sleep(5)
    logger.warning("[超时] 未能识别 TAG 图标，强制继续")
    return False


def linear_boot_vms():
    """线性启动虚拟机，依次等待 TAG 出现后再启动下一台"""
    logger.info("[线性启动] 开始逐台启动虚拟机")
    for i in range(NUM_VMS_TO_START):
        if start_vm(i):
            logger.info(f"[等待] 启动后等待 {VM_BOOT_WAIT} 秒...")
            time.sleep(VM_BOOT_WAIT)
