# 📁 File-Handler-Service 🗃️

The **Amazon S3 file service** of the BearSoft platform. It is the single gateway for reading, writing and deleting files in the data bucket.

-----

## 🎯 Main Purpose

The **File-Handler-Service** concentrates access to S3. Its key features:

  * **Data Reading:** Reads a CSV, Excel (`.xlsx`, `.xls`) or text file and returns its rows; a binary file travels as base64.
  * **Upload and Delete:** Uploads a file to a bucket path and deletes it on request.
  * **Listing:** Lists the bucket's files, with an optional prefix.
  * **Pre-signed URL:** Returns a URL to upload a large file straight to S3, bypassing API Gateway.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Storage:** Amazon S3 (`boto3`)
  * **Data Reading:** pandas, `openpyxl` and `xlrd`
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Files (`/v1/s3`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/s3/read/{bucket_name}/{file_key}` | Reads a **file** and returns its rows. The key may contain folders. |
| `POST` | `/v1/s3/upload` | Uploads a **file** to a bucket path. |
| `DELETE` | `/v1/s3/delete` | Deletes a **file**. |
| `POST` | `/v1/s3/list-files` | Lists the bucket's **files**, with an optional prefix. |
| `POST` | `/v1/s3/upload-presigned` | Returns a **pre-signed URL** to upload straight to S3. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/s3/health` | Service health and configuration check. |

-----

## 🗄️ Stored Data

No tables. The bucket is `ml-data-file-handler`; the folder of each file is chosen by the service that stores it.

-----

## 🧪 Continuous Integration

`.github/workflows/python-package.yml`, on every push and pull request to `main`:
installs `requirements.txt`, runs `pylint --fail-under=10.0 .` **without** the
repository `.pylintrc`, and `pytest` **without `.env`**. `tests/test_files.py` tests the reading with S3 stubbed (CSV with and without a separator, text, base64 binary), the translation of AWS errors and the file key.

-----

## 🗂️ Service Structure

```txt
files/
├── controllers/
│   ├── __init__.py
│   └── files.py
├── routes/
│   ├── __init__.py
│   └── files.py
├── schemas/
│   ├── __init__.py
│   └── files.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── security.py
│   └── utils.py
├── tests/
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── favicon.ico
├── main.py
├── README.md
└── requirements.txt
```

-----

## 📀 Local Setup

To run the service locally:

1.  **Install the dependencies:**

```shell
pip install -r requirements.txt
```

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH` and `ML_DATA_BUCKET_NAME`. It uses the real S3 bucket of the active AWS profile.

3.  **Start the API server:**

```shell
python main.py
```

4.  **Run the tests:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

-----

## 👤 Created By

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
