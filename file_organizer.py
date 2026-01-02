import os
import sys
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import time
import queue
from pathlib import Path

# 1. 定义分类规则
FILE_CATEGORIES = {
    '图片': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'svg'],
    '文档': ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md', 'rtf', 'csv'],
    '压缩包': ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'],
    '视频': ['mp4', 'avi', 'mkv', 'mov', 'flv', 'wmv', 'mpeg', 'mpg', 'webm'],
    '音频': ['mp3', 'wav', 'm4a', 'flac', 'aac', 'ogg', 'wma'],
    '程序': ['py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php', 'json', 'xml'],
    '可执行文件': ['exe', 'msi', 'bat', 'sh', 'app', 'dmg'],
    '其他': []  # 默认分类
}


class FileOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("文件整理工具 v2.0")
        self.root.geometry("800x700")  # 稍微增加窗口高度
        self.root.resizable(True, True)

        # 设置程序图标（可选）
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass

        # 线程安全的消息队列
        self.message_queue = queue.Queue()

        # 设置样式
        self.setup_styles()

        # 创建界面
        self.create_widgets()

        # 状态变量
        self.is_organizing = False
        self.total_files = 0
        self.processed_files = 0

        # 启动消息处理循环
        self.process_messages()

    def setup_styles(self):
        """设置界面样式"""
        style = ttk.Style()
        style.theme_use('clam')

        # 自定义样式
        style.configure("Title.TLabel", font=("Arial", 16, "bold"), foreground="#2c3e50")
        style.configure("Accent.TButton", font=("Arial", 10, "bold"), foreground="white")
        style.map("Accent.TButton", background=[('active', '#2980b9'), ('!disabled', '#3498db')])

    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建可滚动的画布
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 标题
        title_label = ttk.Label(
            scrollable_frame,
            text="📁 文件整理工具",
            style="Title.TLabel"
        )
        title_label.pack(pady=10)

        # 描述
        desc_label = ttk.Label(
            scrollable_frame,
            text="自动将文件按类型分类到相应文件夹中",
            font=("Arial", 10),
            foreground="#7f8c8d"
        )
        desc_label.pack(pady=(0, 15))

        # 文件夹选择部分
        folder_frame = ttk.LabelFrame(scrollable_frame, text="选择文件夹", padding=10)
        folder_frame.pack(fill=tk.X, pady=(0, 15))

        # 路径输入框和浏览按钮
        path_frame = ttk.Frame(folder_frame)
        path_frame.pack(fill=tk.X)

        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(
            path_frame,
            textvariable=self.path_var,
            font=("Arial", 10)
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        browse_btn = ttk.Button(
            path_frame,
            text="浏览...",
            command=self.browse_folder,
            width=10
        )
        browse_btn.pack(side=tk.RIGHT)

        # 选项框架
        options_frame = ttk.LabelFrame(scrollable_frame, text="选项", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        # 是否处理子文件夹选项
        self.recursive_var = tk.BooleanVar(value=False)
        recursive_check = ttk.Checkbutton(
            options_frame,
            text="同时整理子文件夹中的文件",
            variable=self.recursive_var
        )
        recursive_check.pack(anchor=tk.W)

        # 是否跳过错误选项
        self.skip_errors_var = tk.BooleanVar(value=True)
        skip_check = ttk.Checkbutton(
            options_frame,
            text="遇到错误时跳过并继续",
            variable=self.skip_errors_var
        )
        skip_check.pack(anchor=tk.W, pady=(5, 0))

        # 文件分类规则部分 - 简化显示
        rules_frame = ttk.LabelFrame(scrollable_frame, text="文件分类规则", padding=10)
        rules_frame.pack(fill=tk.X, pady=(0, 15))

        # 创建滚动文本框显示分类规则
        rules_text = scrolledtext.ScrolledText(
            rules_frame,
            height=6,  # 减少高度
            font=("Courier", 9),
            wrap=tk.WORD,
            relief=tk.FLAT
        )
        rules_text.pack(fill=tk.X, expand=False)

        # 填充分类规则
        rules_text.insert(tk.END, "当前分类规则：\n")
        rules_text.insert(tk.END, "=" * 40 + "\n")
        for category, extensions in FILE_CATEGORIES.items():
            if extensions:  # 不显示"其他"分类
                rules_text.insert(tk.END, f"\n{category:15}： {', '.join(extensions[:6])}")
                if len(extensions) > 6:
                    rules_text.insert(tk.END, f"\n{' ':15}   {', '.join(extensions[6:12])}")

        rules_text.config(state=tk.DISABLED, background="#f9f9f9")

        # 进度和状态部分
        status_frame = ttk.LabelFrame(scrollable_frame, text="整理进度", padding=10)
        status_frame.pack(fill=tk.X, pady=(0, 15))

        # 进度条框架
        progress_frame = ttk.Frame(status_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        # 进度标签
        self.progress_label = ttk.Label(
            progress_frame,
            text="0%",
            font=("Arial", 9),
            width=5
        )
        self.progress_label.pack(side=tk.RIGHT)

        # 进度条
        self.progress_var = tk.IntVar()
        progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=300
        )
        progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # 状态标签
        self.status_var = tk.StringVar(value="准备就绪")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Arial", 10, "italic")
        )
        status_label.pack()

        # 统计信息标签
        self.stats_var = tk.StringVar(value="")
        stats_label = ttk.Label(
            status_frame,
            textvariable=self.stats_var,
            font=("Arial", 9),
            foreground="#7f8c8d"
        )
        stats_label.pack(pady=(5, 0))

        # 日志文本框 - 减少高度
        log_frame = ttk.LabelFrame(scrollable_frame, text="操作日志", padding=10)
        log_frame.pack(fill=tk.X, pady=(0, 15))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=5,  # 减少高度
            font=("Courier", 9),
            wrap=tk.WORD,
            relief=tk.FLAT
        )
        self.log_text.pack(fill=tk.X, expand=False)
        self.log_text.config(background="#f9f9f9")

        # 按钮框架 - 确保按钮可见
        button_frame = ttk.LabelFrame(scrollable_frame, text="控制面板", padding=15)
        button_frame.pack(fill=tk.X, pady=(0, 10), ipady=5)

        # 第一行按钮
        row1_frame = ttk.Frame(button_frame)
        row1_frame.pack(fill=tk.X, pady=(0, 10))

        # 开始整理按钮
        self.organize_btn = ttk.Button(
            row1_frame,
            text="开始整理",
            command=self.start_organize,
            style="Accent.TButton",
            width=15
        )
        self.organize_btn.pack(side=tk.LEFT, padx=5)

        # 停止按钮
        self.stop_btn = ttk.Button(
            row1_frame,
            text="停止整理",
            command=self.stop_organize,
            state=tk.DISABLED,
            width=15
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # 第二行按钮
        row2_frame = ttk.Frame(button_frame)
        row2_frame.pack(fill=tk.X)

        # 打开文件夹按钮
        self.open_folder_btn = ttk.Button(
            row2_frame,
            text="打开文件夹",
            command=self.open_target_folder,
            width=15
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=5)

        # 清空日志按钮
        clear_log_btn = ttk.Button(
            row2_frame,
            text="清空日志",
            command=self.clear_log,
            width=15
        )
        clear_log_btn.pack(side=tk.LEFT, padx=5)

        # 退出按钮
        exit_btn = ttk.Button(
            row2_frame,
            text="退出程序",
            command=self.root.quit,
            width=15
        )
        exit_btn.pack(side=tk.LEFT, padx=5)

        # 添加一个提示标签，确保按钮区域可见
        tip_label = ttk.Label(
            scrollable_frame,
            text="提示：点击'开始整理'按钮开始整理文件",
            font=("Arial", 9, "italic"),
            foreground="#e74c3c"
        )
        tip_label.pack(pady=(10, 5))

    def process_messages(self):
        """处理消息队列中的消息（线程安全）"""
        try:
            while True:
                message = self.message_queue.get_nowait()
                message_type = message[0]

                if message_type == "log":
                    self._log_message(message[1])
                elif message_type == "progress":
                    self._update_progress(message[1])
                elif message_type == "status":
                    self._update_status(message[1])
                elif message_type == "stats":
                    self._update_stats(message[1])

        except queue.Empty:
            pass

        # 每100ms检查一次消息队列
        self.root.after(100, self.process_messages)

    def _log_message(self, message):
        """线程安全的日志记录"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

        # 限制日志长度，防止内存泄漏
        if self.log_text.index('end-1c').split('.')[0] > '1000':
            self.log_text.delete(1.0, "2.0")

    def _update_progress(self, value):
        """线程安全的进度更新"""
        self.progress_var.set(value)
        self.progress_label.config(text=f"{value}%")

    def _update_status(self, status):
        """线程安全的状态更新"""
        self.status_var.set(status)

    def _update_stats(self, stats):
        """线程安全的统计信息更新"""
        self.stats_var.set(stats)

    def log(self, message):
        """将日志消息放入队列"""
        self.message_queue.put(("log", message))

    def update_progress(self, value):
        """将进度更新放入队列"""
        self.message_queue.put(("progress", value))

    def update_status(self, status):
        """将状态更新放入队列"""
        self.message_queue.put(("status", status))

    def update_stats(self, stats):
        """将统计信息放入队列"""
        self.message_queue.put(("stats", stats))

    def browse_folder(self):
        """打开文件夹选择对话框"""
        folder_selected = filedialog.askdirectory(title="选择要整理的文件夹")
        if folder_selected:
            self.path_var.set(folder_selected)
            self.log(f"已选择文件夹: {folder_selected}")

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        self.log("日志已清空")

    def open_target_folder(self):
        """打开目标文件夹"""
        target_folder = self.path_var.get().strip()
        if target_folder and os.path.exists(target_folder):
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(target_folder)
                elif os.name == 'posix':  # macOS/Linux
                    os.system(f'open "{target_folder}"' if sys.platform == 'darwin' else f'xdg-open "{target_folder}"')
            except Exception as e:
                self.log(f"无法打开文件夹: {e}")
        else:
            messagebox.showwarning("警告", "请先选择有效的文件夹！")

    def start_organize(self):
        """开始整理文件"""
        target_folder = self.path_var.get().strip()

        # 验证文件夹路径
        if not target_folder:
            messagebox.showwarning("警告", "请先选择要整理的文件夹！")
            return

        try:
            target_path = Path(target_folder)
            if not target_path.exists():
                messagebox.showerror("错误", f"文件夹不存在:\n{target_folder}")
                return
            if not target_path.is_dir():
                messagebox.showerror("错误", f"路径不是文件夹:\n{target_folder}")
                return
        except Exception as e:
            messagebox.showerror("错误", f"路径无效:\n{e}")
            return

        # 禁用开始按钮，启用停止按钮
        self.organize_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        # 重置状态
        self.is_organizing = True
        self.processed_files = 0
        self.update_progress(0)
        self.update_stats("")

        # 在新线程中执行整理操作
        self.organize_thread = threading.Thread(
            target=self.organize_files,
            args=(target_folder, self.recursive_var.get(), self.skip_errors_var.get()),
            daemon=True
        )
        self.organize_thread.start()

    def stop_organize(self):
        """停止整理"""
        self.is_organizing = False
        self.update_status("正在停止...")
        self.log("用户请求停止整理操作")

    def collect_files(self, folder_path, recursive=False):
        """收集要整理的文件列表"""
        all_files = []
        folder_path = Path(folder_path)

        try:
            if recursive:
                # 递归收集所有文件
                for root, dirs, files in os.walk(folder_path):
                    # 跳过已经创建的分类文件夹
                    dirs[:] = [d for d in dirs if d not in FILE_CATEGORIES.keys()]

                    for file in files:
                        file_path = Path(root) / file
                        # 跳过分类文件夹中的文件
                        if file_path.parent.name not in FILE_CATEGORIES.keys():
                            all_files.append(str(file_path))
            else:
                # 只收集当前文件夹中的文件
                for item in folder_path.iterdir():
                    if item.is_file():
                        all_files.append(str(item))

        except PermissionError as e:
            self.log(f"权限错误，无法访问文件夹: {e}")
        except Exception as e:
            self.log(f"扫描文件时出错: {e}")

        return all_files

    def organize_files(self, target_folder, recursive=False, skip_errors=True):
        """整理文件的主要逻辑"""
        try:
            self.update_status("正在扫描文件...")
            self.log("开始扫描文件...")

            # 获取所有文件
            all_files = self.collect_files(target_folder, recursive)
            self.total_files = len(all_files)

            if self.total_files == 0:
                self.log("目标文件夹中没有找到可整理的文件。")
                self.update_status("没有找到文件")
                self.finish_organize()
                return

            self.log(f"找到 {self.total_files} 个文件，开始整理...")
            self.update_status(f"正在整理文件 (0/{self.total_files})")

            # 预创建分类文件夹
            for category in FILE_CATEGORIES.keys():
                category_folder = Path(target_folder) / category
                try:
                    if not category_folder.exists():
                        category_folder.mkdir(exist_ok=True)
                        self.log(f"创建文件夹: {category}")
                except Exception as e:
                    self.log(f"创建文件夹 {category} 失败: {e}")

            # 处理每个文件
            moved_files = 0
            skipped_files = 0
            error_files = 0

            for i, file_path in enumerate(all_files):
                if not self.is_organizing:
                    break

                try:
                    file_path = Path(file_path)
                    filename = file_path.name

                    # 获取文件扩展名
                    ext = file_path.suffix.lower().lstrip('.')

                    # 根据扩展名找到对应的分类
                    found_category = '其他'
                    for category, exts in FILE_CATEGORIES.items():
                        if ext in exts:
                            found_category = category
                            break

                    # 目标路径
                    category_folder = Path(target_folder) / found_category
                    target_path = category_folder / filename

                    # 如果目标文件已存在，添加序号
                    counter = 1
                    while target_path.exists():
                        name_parts = file_path.stem.split('_')
                        if len(name_parts) > 1 and name_parts[-1].isdigit():
                            base_name = '_'.join(name_parts[:-1])
                        else:
                            base_name = file_path.stem

                        new_filename = f"{base_name}_{counter}{file_path.suffix}"
                        target_path = category_folder / new_filename
                        counter += 1

                    # 移动文件
                    shutil.move(str(file_path), str(target_path))
                    self.log(f"已移动: {filename} -> {found_category}/")
                    moved_files += 1

                except PermissionError as e:
                    error_msg = f"权限错误，无法移动文件 {filename}: {e}"
                    self.log(error_msg)
                    error_files += 1
                    if not skip_errors:
                        raise
                except shutil.Error as e:
                    error_msg = f"移动文件 {filename} 时出错: {e}"
                    self.log(error_msg)
                    error_files += 1
                    if not skip_errors:
                        raise
                except Exception as e:
                    error_msg = f"处理文件 {filename} 时出错: {e}"
                    self.log(error_msg)
                    error_files += 1
                    if not skip_errors:
                        raise

                # 更新进度
                self.processed_files += 1
                progress_percent = int((self.processed_files / self.total_files) * 100)
                self.update_progress(progress_percent)
                self.update_status(f"正在整理文件 ({self.processed_files}/{self.total_files})")

            # 整理完成
            if self.is_organizing:
                self.log("=" * 40)
                self.log(f"整理完成！")
                self.log(f"成功移动: {moved_files} 个文件")
                self.log(f"跳过文件: {skipped_files} 个")
                self.log(f"错误文件: {error_files} 个")
                self.log("=" * 40)

                stats_text = f"成功: {moved_files} | 跳过: {skipped_files} | 错误: {error_files}"
                self.update_stats(stats_text)
                self.update_status("整理完成")

                messagebox.showinfo("完成",
                                    f"文件整理完成！\n\n"
                                    f"总文件数: {self.total_files}\n"
                                    f"成功移动: {moved_files}\n"
                                    f"跳过文件: {skipped_files}\n"
                                    f"错误文件: {error_files}")
            else:
                self.update_status("整理已停止")
                self.update_stats(f"已处理: {self.processed_files} 个文件")

        except Exception as e:
            self.log(f"整理过程中发生严重错误: {e}")
            self.update_status("整理出错")
            messagebox.showerror("错误", f"整理过程中发生严重错误:\n{e}")

        finally:
            self.finish_organize()

    def finish_organize(self):
        """整理完成后的清理工作"""
        self.is_organizing = False
        self.organize_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)


def main():
    """主函数"""
    root = tk.Tk()
    app = FileOrganizerApp(root)

    # 设置窗口最小大小
    root.minsize(700, 600)

    # 启动主循环
    root.mainloop()


if __name__ == "__main__":
    main()