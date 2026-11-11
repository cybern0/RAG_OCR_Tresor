# parser services
import liteparse

def parse_tabular(): # chunk structured + check for Office software
    pass# return langchain format

def parse_image(): # OCR using PaddleOCR as server + flag has_tabular in image
    pass# return langchain format or array if has structured

def parse_document(): # pdf, word, etc to chunk recursive + check for Office software if not pdf + flag has_tabular in document
    pass # return langchain format or array if has structured