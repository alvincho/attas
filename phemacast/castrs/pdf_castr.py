import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fpdf import FPDF

from phemacast.agents.castr import Castr


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_normalize_text(item) for item in value]
        return "; ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("rendered", "value", "content", "description", "summary", "text"):
            text = _normalize_text(value.get(key))
            if text:
                return text
        if "result" in value:
            label = _normalize_text(value.get("name") or value.get("key") or value.get("pulse_name"))
            text = _normalize_text(value.get("result"))
            if label and text:
                return f"{label}: {text}"
            if text:
                return text
        if "data" in value:
            label = _normalize_text(value.get("name") or value.get("key") or value.get("pulse_name"))
            text = _normalize_text(value.get("data"))
            if label and text:
                return f"{label}: {text}"
            if text:
                return text
        return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return str(value).strip()


def _pdf_safe_text(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    return text.encode("latin-1", "backslashreplace").decode("latin-1")


def _section_lines(section: Dict[str, Any]) -> List[str]:
    lines: List[str] = []

    description = _pdf_safe_text(section.get("description"))
    if description:
        lines.append(description)

    modifier = _pdf_safe_text(section.get("modifier"))
    if modifier:
        lines.append(f"Modifier: {modifier}")

    content = section.get("content", [])
    if isinstance(content, list):
        for item in content:
            text = _pdf_safe_text(item)
            if not text:
                continue
            lines.extend(part.strip() for part in text.splitlines() if part.strip())
    else:
        text = _pdf_safe_text(content)
        if text:
            lines.extend(part.strip() for part in text.splitlines() if part.strip())

    return lines or ["No section content provided."]

class PDFCastr(Castr):
    """
    Specialized Castr for real PDF generation using fpdf2.
    """
    
    def cast(self, phema: Dict[str, Any], format: str, preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a real PDF file from Phema using fpdf2.
        """
        target_format = "PDF"
        media_id = str(uuid.uuid4())
        filename = f"{media_id}.pdf"
        
        if not self.pool or not hasattr(self.pool, "root_path"):
            raise ValueError("FileSystemPool with root_path is required for PDFCastr.")
            
        media_dir = os.path.join(self.pool.root_path, "media")
        os.makedirs(media_dir, exist_ok=True)
        file_path = os.path.join(media_dir, filename)
        
        # Real PDF generation
        self._generate_real_pdf(file_path, phema, preferences)
        
        url = f"/api/media/{filename}"
        
        return {
            "status": "success",
            "media_id": media_id,
            "format": target_format,
            "message": f"Successfully generated real PDF for Phema: {phema.get('name', 'Untitled')}",
            "location": f"media/{filename}",
            "url": url
        }

    def _generate_real_pdf(self, file_path: str, phema: Dict[str, Any], preferences: Optional[Dict[str, Any]] = None):
        """
        Logic for generating a real PDF file using fpdf2.
        """
        pref = preferences or {}
        audience = _pdf_safe_text(pref.get("audience")) or "General"
        language = _pdf_safe_text(pref.get("language")) or "en"
        title = _pdf_safe_text(phema.get("name")) or "Untitled Phema"
        description = _pdf_safe_text(phema.get("description")) or "No description provided."
        
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, "ATTAS Phemacast Report", ln=True, align="C")
        pdf.set_font("helvetica", "I", 10)
        pdf.cell(0, 10, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", ln=True, align="C")
        pdf.ln(5)
        
        # Metadata
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Document Metadata", ln=True)
        pdf.set_font("helvetica", "", 10)
        pdf.cell(0, 8, f"Target Audience: {audience}", ln=True)
        pdf.cell(0, 8, f"Language: {language}", ln=True)
        pdf.cell(0, 8, f"ID: {os.path.basename(file_path)}", ln=True)
        pdf.ln(10)
        
        # Main Content
        pdf.set_font("helvetica", "B", 20)
        pdf.multi_cell(0, 15, title.upper(), align="L")
        pdf.ln(2)
        
        pdf.set_font("helvetica", "I", 12)
        pdf.multi_cell(0, 10, description)
        pdf.ln(10)
        
        # Sections
        sections = phema.get("sections", [])
        for idx, section in enumerate(sections):
            normalized_section = section if isinstance(section, dict) else {
                "name": f"Section {idx+1}",
                "content": [section],
            }
            name = _pdf_safe_text(normalized_section.get("name")) or f"Section {idx+1}"
            content = "\n".join(_section_lines(normalized_section))
            
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(0, 10, f"{idx+1}. {name}", ln=True)
            pdf.set_font("helvetica", "", 11)
            pdf.multi_cell(0, 7, content)
            pdf.ln(5)
        
        # Footer
        pdf.set_y(-30)
        pdf.set_font("helvetica", "I", 8)
        pdf.cell(0, 10, "© 2026 attas | Phemacast Media Engine", align="C", ln=True)
        pdf.cell(0, 5, f"Page {pdf.page_no()}", align="C")
        
        pdf.output(file_path)
