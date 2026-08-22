from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


def _normalize_str(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_na(value: str | None) -> str | None:
    value = _normalize_str(value)
    if value is None or value == "N/A":
        return None
    return value


def _parse_slash_date(value: str | None) -> date | None:
    value = _normalize_str(value)
    if value is None:
        return None
    return datetime.strptime(value.split(" ")[0], "%Y/%m/%d").date()


def _parse_compact_date(value: str | None) -> date | None:
    value = _normalize_str(value)
    if value is None:
        return None
    return datetime.strptime(value, "%Y%m%d").date()


class PatentSearchResult(Base):
    """KIPRIS API 1 (특허/실용신안 검색) 결과 캐시."""

    __tablename__ = "patent_search_results"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    application_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
    )

    applicant_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        index=True,
    )

    application_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    astrt_cont: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    big_drawing: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    drawing: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    index_no: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    invention_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    ipc_number: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    open_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    open_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    publication_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    publication_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    register_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    register_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    register_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @classmethod
    def from_kipris_json(cls, data: dict) -> "PatentSearchResult":
        index_no = data.get("indexNo")
        return cls(
            application_number=data["applicationNumber"],
            applicant_name=_normalize_str(data.get("applicantName")),
            application_date=_parse_slash_date(data.get("applicationDate")),
            astrt_cont=_normalize_str(data.get("astrtCont")),
            big_drawing=_normalize_str(data.get("bigDrawing")),
            drawing=_normalize_str(data.get("drawing")),
            index_no=int(index_no) if index_no not in (None, "") else None,
            invention_title=data["inventionTitle"],
            ipc_number=_normalize_str(data.get("ipcNumber")),
            open_date=_parse_slash_date(data.get("openDate")),
            open_number=_normalize_str(data.get("openNumber")),
            publication_date=_parse_slash_date(data.get("publicationDate")),
            publication_number=_normalize_str(data.get("publicationNumber")),
            register_date=_parse_slash_date(data.get("registerDate")),
            register_number=_normalize_str(data.get("registerNumber")),
            register_status=_normalize_str(data.get("registerStatus")),
        )


class PatentAdministrativeHistory(Base):
    """KIPRIS API 6 (행정처리 이력/관련 문헌) 결과 캐시."""

    __tablename__ = "patent_administrative_histories"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    application_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    document_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        unique=True,
        index=True,
    )

    document_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    document_title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    document_title_eng: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status_eng: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    step: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    trial_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    registration_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @classmethod
    def from_kipris_json(cls, data: dict) -> "PatentAdministrativeHistory":
        return cls(
            application_number=data["applicationNumber"],
            document_number=data["documentNumber"],
            document_date=_parse_compact_date(data.get("documentDate")),
            document_title=_normalize_str(data.get("documentTitle")),
            document_title_eng=_normalize_str(data.get("documentTitleEng")),
            status=_normalize_str(data.get("status")),
            status_eng=_normalize_str(data.get("statusEng")),
            step=_normalize_str(data.get("step")),
            trial_number=_normalize_na(data.get("trialNumber")),
            registration_number=_normalize_na(data.get("registrationNumber")),
        )