'''
    Portal seeding package.

    Imports the WordPress public REST API of mineria.gob.bo, parses each
    detail page to recover body/assets, re-uploads binaries to the FILES
    microservice, and finally POSTs structured items to the CMS admin
    endpoints. One-shot by design; safe to re-run after `--wipe`.
'''
