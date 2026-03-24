import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fpdf import FPDF

from phemacast.agents.castr import Castr

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
        audience = pref.get("audience", "General")
        language = pref.get("language", "en")
        
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
        pdf.multi_cell(0, 15, phema.get("name", "Untitled Phema").upper(), align="L")
        pdf.ln(2)
        
        pdf.set_font("helvetica", "I", 12)
        pdf.multi_cell(0, 10, phema.get("description", "No description provided."))
        pdf.ln(10)
        
        # Sections
        sections = phema.get("sections", [])
        for idx, section in enumerate(sections):
            name = section.get("name", f"Section {idx+1}")
            content = section.get("content", "")
            
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
