"""
MS Office Automation Tools for Casper
Uses win32com to natively control Word, Excel, and PowerPoint on Windows.
"""

import os
import logging
from typing import Optional
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("office-tools")

# Attempt to import win32com
try:
    import win32com.client
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    logger.warning("win32com.client not available. Please pip install pywin32")

# Default save directory
DEFAULT_SAVE_DIR = os.path.expanduser(r"~\Documents\Cipher\Casper_Docs")
os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)


def _get_app(app_name: str, visible: bool = False):
    """Helper to dispatch and get the COM app."""
    if not WIN32_AVAILABLE:
        raise RuntimeError("win32com.client is not installed on this system.")
    app = win32com.client.Dispatch(app_name)
    app.Visible = visible
    return app


# ==========================================
# GENERAL OFFICE TOOLS
# ==========================================

@function_tool()
async def office_close_app(context: RunContext, app_name: str) -> str:
    """
    Close an Office application by name.
    
    Args:
        app_name: "Word", "Excel", or "PowerPoint"
    """
    if not WIN32_AVAILABLE:
        return "win32com not available."
    
    name_map = {
        "word": "Word.Application",
        "excel": "Excel.Application",
        "powerpoint": "PowerPoint.Application"
    }
    
    app_id = name_map.get(app_name.lower())
    if not app_id:
        return f"Unsupported app: {app_name}. Use Word, Excel, or PowerPoint."
        
    try:
        # Get existing instance if running
        app = win32com.client.GetActiveObject(app_id)
        app.Quit()
        return f"Successfully closed {app_name}."
    except Exception as e:
        return f"Failed to close {app_name}. It might not be running. Error: {str(e)}"


# ==========================================
# MICROSOFT WORD TOOLS
# ==========================================

@function_tool()
async def word_create_document(context: RunContext, text: str) -> str:
    """
    Open MS Word, create a new document, and type the provided text.
    
    Args:
        text: The text to insert into the document.
    """
    try:
        word = _get_app("Word.Application", visible=False)
        doc = word.Documents.Add()
        # Insert text at the end of the document
        selection = word.Selection
        selection.TypeText(text)
        
        # Reveal when done
        word.Visible = True
        return "Successfully created Word document and inserted text."
    except Exception as e:
        logger.error(f"Word automation failed: {e}")
        return f"Failed to create Word document: {str(e)}"


@function_tool()
async def word_read_active_document(context: RunContext) -> str:
    """
    Read all the text from the currently active MS Word document.
    """
    try:
        word = win32com.client.GetActiveObject("Word.Application")
        if not word.Documents.Count:
            return "No documents are currently open in Word."
        
        doc = word.ActiveDocument
        content = doc.Content.Text
        return f"Document Content:\n{content}"
    except Exception as e:
        return f"Failed to read Word document. Is Word open? Error: {str(e)}"


@function_tool()
async def word_save_document(context: RunContext, file_name: str) -> str:
    """
    Save the currently active MS Word document.
    
    Args:
        file_name: The name of the file (e.g., 'report.docx'). It will be saved in Documents/Cipher/Casper_Docs.
    """
    try:
        word = win32com.client.GetActiveObject("Word.Application")
        if not word.Documents.Count:
            return "No documents are currently open in Word."
        
        doc = word.ActiveDocument
        if not file_name.endswith(".docx"):
            file_name += ".docx"
            
        full_path = os.path.join(DEFAULT_SAVE_DIR, file_name)
        # 16 is wdFormatDocumentDefault
        doc.SaveAs2(full_path, 16)
        return f"Document saved successfully at: {full_path}"
    except Exception as e:
        return f"Failed to save document: {str(e)}"


# ==========================================
# MICROSOFT EXCEL TOOLS
# ==========================================

@function_tool()
async def excel_create_workbook(context: RunContext, data_csv: str) -> str:
    """
    Open MS Excel, create a new workbook, and populate it with comma-separated data.
    
    Args:
        data_csv: Multiline string of comma-separated data to insert.
    """
    try:
        excel = _get_app("Excel.Application", visible=False)
        wb = excel.Workbooks.Add()
        sheet = wb.ActiveSheet
        
        # Parse simple CSV and write to cells
        rows = data_csv.strip().split('\n')
        for r_idx, row in enumerate(rows):
            cols = row.split(',')
            for c_idx, val in enumerate(cols):
                sheet.Cells(r_idx + 1, c_idx + 1).Value = val.strip()
                
        # Auto-fit columns
        sheet.Columns.AutoFit()
        
        # Reveal when done
        excel.Visible = True
        return "Successfully created Excel workbook and inserted data."
    except Exception as e:
        logger.error(f"Excel automation failed: {e}")
        return f"Failed to create Excel workbook: {str(e)}"


@function_tool()
async def excel_read_active_sheet(context: RunContext) -> str:
    """
    Read the used range of the currently active MS Excel worksheet.
    """
    try:
        excel = win32com.client.GetActiveObject("Excel.Application")
        if not excel.Workbooks.Count:
            return "No workbooks are currently open in Excel."
            
        sheet = excel.ActiveSheet
        used_range = sheet.UsedRange
        
        if not used_range:
            return "Active sheet is empty."
            
        # used_range() returns a tuple of tuples representing rows and columns
        data = used_range.Value
        if not data:
            return "Active sheet is empty."
            
        result = []
        # Handle single cell vs multi-cell return values
        if isinstance(data, tuple):
            for row in data:
                row_strs = [str(cell) if cell is not None else "" for cell in row]
                result.append(" | ".join(row_strs))
        else:
            result.append(str(data))
            
        return "Excel Data:\n" + "\n".join(result)
    except Exception as e:
        return f"Failed to read Excel data. Is Excel open? Error: {str(e)}"


# ==========================================
# MICROSOFT POWERPOINT TOOLS
# ==========================================

@function_tool()
async def ppt_create_presentation(context: RunContext, title: str, subtitle: str) -> str:
    """
    Open MS PowerPoint, create a new presentation, and add a title slide.
    
    Args:
        title: Main title for the presentation.
        subtitle: Subtitle for the presentation.
    """
    try:
        ppt = _get_app("PowerPoint.Application", visible=False)
        pres = ppt.Presentations.Add()
        # 1 is ppLayoutTitle
        slide = pres.Slides.Add(1, 1)
        
        slide.Shapes.Title.TextFrame.TextRange.Text = title
        if slide.Shapes.Count >= 2:
            slide.Shapes(2).TextFrame.TextRange.Text = subtitle
            
        # Reveal when done
        ppt.Visible = True
        return "Successfully created PowerPoint presentation."
    except Exception as e:
        logger.error(f"PowerPoint automation failed: {e}")
        return f"Failed to create PowerPoint: {str(e)}"


# Export all tools
OFFICE_TOOLS = [
    office_close_app,
    word_create_document,
    word_read_active_document,
    word_save_document,
    excel_create_workbook,
    excel_read_active_sheet,
    ppt_create_presentation
]
