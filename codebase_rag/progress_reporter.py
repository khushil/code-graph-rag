"""Progress reporting for parallel processing operations."""

import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from typing import Callable, Optional

from loguru import logger


@dataclass
class ProgressStats:
    """Statistics for progress tracking."""
    total_items: int
    processed_items: int
    failed_items: int
    start_time: datetime
    current_phase: str
    items_per_second: float = 0.0
    estimated_time_remaining: Optional[timedelta] = None


class ProgressReporter:
    """Reports progress for long-running operations (REQ-SCL-2)."""
    
    def __init__(self, 
                 total_items: int,
                 update_interval: float = 1.0,
                 show_eta: bool = True,
                 show_rate: bool = True):
        self.total_items = total_items
        self.processed_items = 0
        self.failed_items = 0
        self.update_interval = update_interval
        self.show_eta = show_eta
        self.show_rate = show_rate
        
        self.start_time = datetime.now()
        self.current_phase = "Initializing"
        self.last_update_time = time.time()
        self.last_processed_count = 0
        
        self._lock = Lock()
        self._stop_event = Event()
        self._reporter_thread: Optional[Thread] = None
        
    def start(self) -> None:
        """Start the progress reporter thread."""
        if self._reporter_thread is None or not self._reporter_thread.is_alive():
            self._stop_event.clear()
            self._reporter_thread = Thread(target=self._report_loop, daemon=True)
            self._reporter_thread.start()
            logger.info(f"Progress reporter started for {self.total_items} items")
    
    def stop(self) -> None:
        """Stop the progress reporter thread."""
        self._stop_event.set()
        if self._reporter_thread:
            self._reporter_thread.join(timeout=2.0)
        self._print_final_report()
    
    def update(self, processed: int = 1, failed: int = 0) -> None:
        """Update progress counters."""
        with self._lock:
            self.processed_items += processed
            self.failed_items += failed
    
    def set_phase(self, phase: str) -> None:
        """Set the current processing phase."""
        with self._lock:
            self.current_phase = phase
            logger.info(f"Phase changed to: {phase}")
    
    def get_stats(self) -> ProgressStats:
        """Get current progress statistics."""
        with self._lock:
            elapsed = datetime.now() - self.start_time
            
            # Calculate rate
            if elapsed.total_seconds() > 0:
                items_per_second = self.processed_items / elapsed.total_seconds()
            else:
                items_per_second = 0.0
            
            # Estimate time remaining
            if items_per_second > 0 and self.processed_items < self.total_items:
                remaining_items = self.total_items - self.processed_items
                estimated_seconds = remaining_items / items_per_second
                estimated_time_remaining = timedelta(seconds=estimated_seconds)
            else:
                estimated_time_remaining = None
            
            return ProgressStats(
                total_items=self.total_items,
                processed_items=self.processed_items,
                failed_items=self.failed_items,
                start_time=self.start_time,
                current_phase=self.current_phase,
                items_per_second=items_per_second,
                estimated_time_remaining=estimated_time_remaining
            )
    
    def _report_loop(self) -> None:
        """Main loop for reporting progress."""
        while not self._stop_event.is_set():
            current_time = time.time()
            
            # Only update if enough time has passed
            if current_time - self.last_update_time >= self.update_interval:
                self._print_progress()
                self.last_update_time = current_time
            
            # Sleep briefly to avoid busy waiting
            time.sleep(0.1)
    
    def _print_progress(self) -> None:
        """Print current progress to console."""
        stats = self.get_stats()
        
        # Calculate percentage
        if stats.total_items > 0:
            percentage = (stats.processed_items / stats.total_items) * 100
        else:
            percentage = 0
        
        # Build progress message
        parts = [
            f"\r[{stats.current_phase}]",
            f"{stats.processed_items}/{stats.total_items}",
            f"({percentage:.1f}%)"
        ]
        
        if stats.failed_items > 0:
            parts.append(f"[{stats.failed_items} failed]")
        
        if self.show_rate and stats.items_per_second > 0:
            parts.append(f"[{stats.items_per_second:.1f} items/s]")
        
        if self.show_eta and stats.estimated_time_remaining:
            eta_str = self._format_timedelta(stats.estimated_time_remaining)
            parts.append(f"[ETA: {eta_str}]")
        
        # Print with carriage return to overwrite previous line
        message = " ".join(parts)
        sys.stdout.write(f"{message:<80}")  # Pad to clear previous content
        sys.stdout.flush()
    
    def _print_final_report(self) -> None:
        """Print final summary report."""
        stats = self.get_stats()
        elapsed = datetime.now() - stats.start_time
        
        # Clear the progress line
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        
        # Print summary
        logger.info(f"Processing completed:")
        logger.info(f"  Total items: {stats.total_items}")
        logger.info(f"  Processed: {stats.processed_items}")
        logger.info(f"  Failed: {stats.failed_items}")
        logger.info(f"  Success rate: {((stats.processed_items - stats.failed_items) / max(1, stats.total_items)) * 100:.1f}%")
        logger.info(f"  Total time: {self._format_timedelta(elapsed)}")
        
        if stats.items_per_second > 0:
            logger.info(f"  Average rate: {stats.items_per_second:.1f} items/s")
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


class BatchProgressReporter(ProgressReporter):
    """Progress reporter optimized for batch operations."""
    
    def __init__(self, 
                 total_items: int,
                 batch_size: int,
                 **kwargs):
        super().__init__(total_items, **kwargs)
        self.batch_size = batch_size
        self.current_batch = 0
        self.total_batches = (total_items + batch_size - 1) // batch_size
    
    def start_batch(self, batch_num: int) -> None:
        """Mark the start of a new batch."""
        with self._lock:
            self.current_batch = batch_num
            self.set_phase(f"Processing batch {batch_num}/{self.total_batches}")
    
    def complete_batch(self, batch_num: int, items_in_batch: int) -> None:
        """Mark a batch as complete."""
        self.update(processed=items_in_batch)
        logger.debug(f"Completed batch {batch_num} with {items_in_batch} items")