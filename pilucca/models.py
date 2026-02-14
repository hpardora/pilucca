from datetime import datetime, date

from pydantic import BaseModel, RootModel, Field, EmailStr
from typing import List, Optional, Dict

class AuthToken(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    scope: str

class LuccaAuthToken(BaseModel):
    authToken: str
    expiration: str

class LuccaUserInfo(BaseModel):
    sub: str
    instance_uri: str
    user_local_id: int
    is_impersonation: bool
    email: str
    lu_full_name: str
    given_name: str
    family_name: str
    lu_establishment_id: int
    culture: str
    lu_employee_status: str

class PrincipalResponse(BaseModel):
    id: int
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    full_name: str = Field(alias="fullName")
    mail: EmailStr
    culture_code: str = Field(alias="cultureCode")
    establishment_id: int = Field(alias="establishmentId")
    session_expires_at: datetime = Field(alias="sessionExpiresAt")
    session_expires_at_utc: datetime = Field(alias="sessionExpiresAtUtc")
    is_multi_profile_account: bool = Field(alias="isMultiProfileAccount")

class UserInputConfiguration(BaseModel):
    authorizedInputInterval: AuthorizedInputInterval
    allowComments: bool

class AuthorizedInputInterval(BaseModel):
    start: date
    end: date
    allowInputPastWithoutEdition: bool
    allowInputDaysOff: bool

class Department(BaseModel):
    id: Optional[int] = 0
    name: str

class Owner(BaseModel):
    id: int
    lastName: str
    firstName: str
    department: Department
    pictureUrl: Optional[str] = None

class WorkLocation(BaseModel):
    id: int
    name: str
    color: str
    colorHexa: str

class Floor(BaseModel):
    id: int
    key: int
    name: str
    mapFileId: str
    mapFileUrl: str  # Can use HttpUrl if it's a full URL

class UserLocation(BaseModel):
    isUrgent: bool
    isPast: bool
    id: int
    owner: Owner
    workLocation: Optional[WorkLocation] = None
    area: Optional[Department] = None # Area follows the same id/name structure
    floors: Optional[List[Floor]] = []
    status: str
    ownerId: int
    workLocationId: int
    areaId: Optional[int] = 0
    position: str
    date: date

class FullDayContainer(BaseModel):
    userLocation: Optional[UserLocation] = None
    type: str
    name: str

class DayEntry(BaseModel):
    fullDay: Optional[FullDayContainer] = None
    date: date
    type: str


class WorkLocationTimeline(RootModel):
    # This maps the dynamic date strings to DayEntry objects
    root: Dict[str, DayEntry]

class WorkLocationFromTemplate(BaseModel):
    saved: bool
    isApprovalRequired: bool
    warnings: Optional[List[str]] = []
    exceededRules: Optional[List[str]] = []
    overbookings: Optional[List[str]] = []

class UpdatedResult(BaseModel):
    success: bool
    start_date: date
    end_date: date