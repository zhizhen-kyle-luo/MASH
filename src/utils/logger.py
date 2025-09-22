import logging
import sys
from pathlib import Path
from datetime import datetime
from pythonjsonlogger import jsonlogger
import os


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the specified name"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Set log level from environment
        log_level = os.getenv("LOG_LEVEL", "INFO")
        logger.setLevel(getattr(logging, log_level))
        
        # Console handler with JSON formatting
        console_handler = logging.StreamHandler(sys.stdout)
        
        # JSON formatter for structured logging
        json_formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(json_formatter)
        logger.addHandler(console_handler)
        
        # File handler for transcripts
        transcript_dir = Path(os.getenv("TRANSCRIPT_DIR", "./transcripts"))
        transcript_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(
            transcript_dir / f"mash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)
        
        logger.propagate = False
    
    return logger


class TranscriptLogger:
    """Logger specifically for conversation transcripts"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.transcript_dir = Path(os.getenv("TRANSCRIPT_DIR", "./transcripts"))
        self.transcript_dir.mkdir(exist_ok=True)
        self.filepath = self.transcript_dir / f"{session_id}.jsonl"
        
    def log_message(self, message_dict: dict):
        """Log a message to the transcript file"""
        import json
        with open(self.filepath, 'a') as f:
            f.write(json.dumps(message_dict, default=str) + '\n')
            
    def get_transcript(self) -> list:
        """Read the full transcript"""
        import json
        if not self.filepath.exists():
            return []
            
        with open(self.filepath, 'r') as f:
            return [json.loads(line) for line in f]