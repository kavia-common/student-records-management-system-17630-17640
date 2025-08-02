from fastapi import FastAPI, HTTPException, Query, Path, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import uuid

# =========================
# Models
# =========================

# PUBLIC_INTERFACE
class StudentIn(BaseModel):
    """Request model for creating/updating a student."""
    name: str = Field(..., min_length=1, max_length=100, description="The full name of the student")
    student_class: str = Field(..., min_length=1, max_length=20, description="The class or section the student belongs to (e.g., '10A')")
    marks: int = Field(..., ge=0, le=100, description="The marks scored by the student (0-100)")

    # PUBLIC_INTERFACE
    @validator("name")
    def strip_and_validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty or whitespace")
        return v

    # PUBLIC_INTERFACE
    @validator("student_class")
    def strip_and_validate_class(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Student class cannot be empty or whitespace")
        return v


# PUBLIC_INTERFACE
class StudentOut(StudentIn):
    """Response model for student, with unique ID."""
    id: str = Field(..., description="The unique identifier of the student")


# PUBLIC_INTERFACE
class StatusResponse(BaseModel):
    """Status message model."""
    success: bool
    message: str
    data: Optional[Any] = None


# =========================
# Application Initialization
# =========================

app = FastAPI(
    title="Student Management Backend API",
    description="Backend REST API for managing students with in-memory storage.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Students", "description": "Operations related to students"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for API access; adjust for production
    allow_credentials=False,  # Important: credentials must be False with wildcard origins according to CORS spec
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# In-memory Storage
# =========================

students: Dict[str, StudentOut] = {}  # {id: StudentOut}


# =========================
# API Endpoints
# =========================

@app.get("/", summary="Health Check", tags=["Health"])
def health_check():
    """Simple health check."""
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.get("/students", response_model=List[StudentOut], summary="List students", tags=["Students"])
def get_students(
    sort_by: Optional[str] = Query(None, description="Sort field: name, class, or marks"),
    order: Optional[str] = Query("asc", description="asc for ascending, desc for descending"),
    filter_class: Optional[str] = Query(None, alias="class", description="Filter by class/section"),
    min_marks: Optional[int] = Query(None, ge=0, le=100, description="Filter students with marks >= min_marks"),
    max_marks: Optional[int] = Query(None, ge=0, le=100, description="Filter students with marks <= max_marks")
):
    """
    Get a list of students, with optional sorting and filtering by class or marks.
    """
    result = list(students.values())

    # Filtering
    if filter_class is not None:
        result = [stud for stud in result if stud.student_class == filter_class]
    if min_marks is not None:
        result = [stud for stud in result if stud.marks >= min_marks]
    if max_marks is not None:
        result = [stud for stud in result if stud.marks <= max_marks]

    # Sorting
    if sort_by is not None:
        sort_attr = sort_by.lower()
        if sort_attr in {"name", "marks", "student_class"}:
            reverse = (order == "desc")
            key_map = {
                "name": lambda s: s.name.lower(),
                "marks": lambda s: s.marks,
                "student_class": lambda s: s.student_class.lower()
            }
            result.sort(key=key_map[sort_attr], reverse=reverse)
        else:
            raise HTTPException(status_code=400, detail="Invalid sort_by field")

    return result


# PUBLIC_INTERFACE
@app.post(
    "/students",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new student",
    tags=["Students"],
)
def create_student(student: StudentIn):
    """
    Add a new student to the records.
    """
    # Optionally, check uniqueness by name+class (can be relaxed)
    # Prevent duplicate name+class (optional; relax if needed)
    for s in students.values():
        if s.name.lower() == student.name.lower() and s.student_class.lower() == student.student_class.lower():
            return StatusResponse(
                success=False,
                message="A student with this name and class already exists.",
                data=None
            )

    student_id = str(uuid.uuid4())
    student_out = StudentOut(id=student_id, **student.dict())
    students[student_id] = student_out
    return StatusResponse(
        success=True,
        message="Student created successfully.",
        data=student_out
    )


# PUBLIC_INTERFACE
@app.put(
    "/students/{student_id}",
    response_model=StatusResponse,
    summary="Update existing student",
    tags=["Students"],
)
def update_student(
    student_id: str = Path(..., description="ID of the student to update"),
    updated: StudentIn = ...,
):
    """
    Update an existing student by ID.
    """
    if student_id not in students:
        return StatusResponse(
            success=False,
            message="Student not found.",
            data=None
        )
    # Optional: Check for name/class collision with *other* students
    for sid, s in students.items():
        if sid != student_id and s.name.lower() == updated.name.lower() and s.student_class.lower() == updated.student_class.lower():
            return StatusResponse(
                success=False,
                message="A student with this name and class already exists.",
                data=None
            )
    updated_student = StudentOut(id=student_id, **updated.dict())
    students[student_id] = updated_student
    return StatusResponse(
        success=True,
        message="Student updated successfully.",
        data=updated_student
    )


# PUBLIC_INTERFACE
@app.delete(
    "/students/{student_id}",
    response_model=StatusResponse,
    summary="Delete a student",
    tags=["Students"],
)
def delete_student(
    student_id: str = Path(..., description="ID of the student to delete")
):
    """
    Delete a student by ID. Returns status message.
    """
    if student_id not in students:
        return StatusResponse(
            success=False,
            message="Student not found.",
            data=None
        )
    removed = students.pop(student_id)
    return StatusResponse(
        success=True,
        message="Student deleted successfully.",
        data=removed
    )

# PUBLIC_INTERFACE
@app.get(
    "/students/{student_id}",
    response_model=StatusResponse,
    summary="Retrieve single student by ID",
    tags=["Students"],
)
def get_student_by_id(
    student_id: str = Path(..., description="ID of the student to retrieve")
):
    """
    Get details of a single student by ID.
    """
    student = students.get(student_id)
    if student is None:
        return StatusResponse(
            success=False,
            message="Student not found.",
            data=None
        )
    return StatusResponse(
        success=True,
        message="Student retrieved successfully.",
        data=student
    )
