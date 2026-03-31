import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utils.config import Config
from utils.telegram_notifier import notifier

# Get logger, do not configure basicConfig here
logger = logging.getLogger("ReportWatcher")

class ReportFileHandler(FileSystemEventHandler):
    """Handle file system events in the reports directory."""

    def __init__(self, watch_dir: str):
        self.watch_dir = watch_dir
        self.processed_files = set()  # Simple in-memory deduplication

    def on_created(self, event):
        if not event.is_directory:
            self._process_event(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._process_event(event.src_path)

    def _process_event(self, file_path: str):
        """Core processing logic."""
        # Only process Markdown files
        if not file_path.endswith('.md'):
            return

        # First priority: by default only push overview.md
        if 'overview.md' not in file_path.lower():
            return

        # Memory deduplication (based on path)
        if file_path in self.processed_files:
            return

        logger.info(f"Detected new report file: {file_path}")
        
        # Wait for file writing to stabilize
        if self._wait_until_file_stable(file_path):
            logger.info(f"File stabilized, starting push: {file_path}")
            notifier.push_report(file_path)
            self.processed_files.add(file_path)
        else:
            logger.warning(f"File failed to stabilize within the specified time, giving up push: {file_path}")

    def _wait_until_file_stable(self, file_path: str, timeout: int = 10) -> bool:
        """Check if file size has stopped growing to ensure writing is complete."""
        start_time = time.time()
        last_size = -1
        
        while time.time() - start_time < timeout:
            try:
                current_size = os.path.getsize(file_path)
                if current_size > 0 and current_size == last_size:
                    # File size is consistent twice and not zero, consider stable
                    return True
                last_size = current_size
            except OSError:
                # File may not have been fully created yet
                pass
            time.sleep(1)
        return False

def start_report_watcher():
    """Start the report directory watcher."""
    watch_dir = Config.REPORT_WATCH_DIR
    if not os.path.exists(watch_dir):
        os.makedirs(watch_dir, exist_ok=True)

    logger.info(f"Starting report watcher, watching directory: {os.path.abspath(watch_dir)}")
    
    # Check configuration
    if not notifier.is_enabled():
        logger.error("Telegram configuration is missing, watcher will start but cannot send messages!")

    event_handler = ReportFileHandler(watch_dir)
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=True)
    observer.start()
    
    logger.info("Watcher is running in the background. Press Ctrl+C to stop (if running in main thread).")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Watcher has been stopped.")
    observer.join()

if __name__ == "__main__":
    # Only configure logging when running standalone
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    start_report_watcher()
