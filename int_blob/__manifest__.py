{
    "name": "Blob storage",
    "summary": "Streaming uploads of large files into the attachment filestore.",
    "description": (
        "Extends the attachments with a way to store a file from a stream, block by block, "
        "without holding it in memory. Storage, cleaning, download and access rights stay "
        "those of the core."
    ),
    "version": "19.0.1.0.0",
    "category": "Hidden/Tools",
    "author": "Waldemar Toews",
    "license": "LGPL-3",
    "depends": ["base"],
    "installable": True,
    "application": False,
}
