# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
import models

def is_run_id_unique(db: Session, run_id: str) -> bool:
    """Check if a given run ID already exists in the database."""
    return db.query(models.Run).filter(models.Run.id == run_id).first() is None

def create_new_run(db: Session, run_id: str, patent_ids: list[str]):
    """Create a new pending run record in the database."""
    new_run = models.Run(id=run_id, status="pending", input_ids=patent_ids)
    db.add(new_run)
    db.commit()

def get_run_status(db: Session, run_id: str):
    """Fetch only the status and error message for a run to save bandwidth."""
    return db.query(models.Run.status, models.Run.error_message).filter(models.Run.id == run_id).first()

def get_run_taxonomy(db: Session, run_id: str):
    """Fetch only the status and final taxonomy for a run."""
    return db.query(models.Run.status, models.Run.final_taxonomy).filter(models.Run.id == run_id).first()

def get_run_for_excel(db: Session, run_id: str):
    """Fetch all necessary data for Excel generation, avoiding the final_taxonomy JSON."""
    return db.query(
        models.Run.status, 
        models.Run.source_data, 
        models.Run.is_pubmed, 
        models.Run.input_ids
    ).filter(models.Run.id == run_id).first()

def update_run_status_running(db: Session, run_id: str):
    """Update a run's status to running."""
    db.query(models.Run).filter(models.Run.id == run_id).update({"status": "running"})
    db.commit()

def update_run_status_completed(db: Session, run_id: str, final_taxonomy: list, source_data: dict, is_pubmed: bool):
    """Update a run's status to completed with all final output data."""
    db.query(models.Run).filter(models.Run.id == run_id).update({
        "status": "completed",
        "final_taxonomy": final_taxonomy,
        "source_data": source_data,
        "is_pubmed": is_pubmed
    })
    db.commit()

def update_run_status_failed(db: Session, run_id: str, error_message: str):
    """Update a run's status to failed with the error message."""
    db.query(models.Run).filter(models.Run.id == run_id).update({
        "status": "failed",
        "error_message": error_message
    })
    db.commit()
