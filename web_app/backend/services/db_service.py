# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
import models

def is_run_id_unique(db: Session, run_id: str) -> bool:
    """Check if a given run ID already exists in the database."""
    return db.query(models.Run).filter(models.Run.id == run_id).first() is None

def create_new_run(db: Session, run_id: str, patent_ids: list[str], user_id: int):
    """Create a new pending run record in the database linked to a specific user."""
    is_pubmed = any(pid.isdigit() for pid in patent_ids) if patent_ids else False
    name = f"{'PubMed' if is_pubmed else 'Patent'} Graph"
    if patent_ids:
        name += f" ({len(patent_ids)} items)"
        
    new_run = models.Run(id=run_id, status="pending", input_ids=patent_ids, user_id=user_id, name=name, is_pubmed=is_pubmed)
    db.add(new_run)
    db.commit()

def get_run_status(db: Session, run_id: str, user_id: int):
    """Fetch only the status and error message for a run to save bandwidth, ensuring the user owns it."""
    return db.query(models.Run.status, models.Run.error_message).filter(models.Run.id == run_id, models.Run.user_id == user_id).first()

def get_run_taxonomy(db: Session, run_id: str, user_id: int):
    """Fetch only the status and final taxonomy for a run, ensuring the user owns it."""
    return db.query(models.Run.status, models.Run.final_taxonomy, models.Run.name).filter(models.Run.id == run_id, models.Run.user_id == user_id).first()

def get_runs_by_user(db: Session, user_id: int):
    """Fetch lightweight run history for the dashboard for a specific user."""
    runs = db.query(
        models.Run.id, 
        models.Run.status, 
        models.Run.is_pubmed, 
        models.Run.created_at,
        models.Run.error_message,
        models.Run.name
    ).filter(models.Run.user_id == user_id).order_by(models.Run.created_at.desc()).all()
    
    return [
        {
            "id": r.id,
            "name": r.name or ("PubMed Graph" if r.is_pubmed else "Patent Graph"),
            "status": r.status,
            "is_pubmed": r.is_pubmed,
            "created_at": r.created_at,
            "error_message": r.error_message
        } for r in runs
    ]

def get_run_for_excel(db: Session, run_id: str, user_id: int):
    """Fetch all necessary data for Excel generation, avoiding the final_taxonomy JSON, ensuring the user owns it."""
    return db.query(
        models.Run.status, 
        models.Run.source_data, 
        models.Run.is_pubmed, 
        models.Run.input_ids,
        models.Run.name
    ).filter(models.Run.id == run_id, models.Run.user_id == user_id).first()

def update_run_status_running(db: Session, run_id: str):
    """Update a run's status to running."""
    db.query(models.Run).filter(models.Run.id == run_id).update({"status": "running"})
    db.commit()

def update_run_status_completed(db: Session, run_id: str, final_taxonomy: list, source_data: dict, is_pubmed: bool, meaningful_name: str = None):
    """Update a run's status to completed with all final output data."""
    update_data = {
        "status": "completed",
        "final_taxonomy": final_taxonomy,
        "source_data": source_data,
        "is_pubmed": is_pubmed
    }
    if meaningful_name:
        update_data["name"] = meaningful_name
        
    db.query(models.Run).filter(models.Run.id == run_id).update(update_data)
    db.commit()

def update_run_status_failed(db: Session, run_id: str, error_message: str):
    """Update a run's status to failed with the error message."""
    db.query(models.Run).filter(models.Run.id == run_id).update({
        "status": "failed",
        "error_message": error_message
    })
    db.commit()
