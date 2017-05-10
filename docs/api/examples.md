# API Examples

Supported HTTP methods:

* `GET`: Retrieve an object or list of objects
* `POST`: Create a new object
* `PUT`: Update an existing object
* `DELETE`: Delete an existing object

To authenticate a request, attach your token in an `Authorization` header:

```
curl -H "Authorization: Token d2f763479f703d80de0ec15254237bc651f9cdc0"
```

### Retrieving a list of sites

Send a `GET` request to the object list endpoint. The response contains a paginated list of JSON objects.

```
$ curl -H "Accept: application/json; indent=4" http://localhost/api/dcim/sites/
{
    "count": 14,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 6,
            "name": "Corporate HQ",
            "slug": "corporate-hq",
            "region": null,
            "tenant": null,
            "facility": "",
            "asn": null,
            "physical_address": "742 Evergreen Terrace, Springfield, USA",
            "shipping_address": "",
            "contact_name": "",
            "contact_phone": "",
            "contact_email": "",
            "comments": "",
            "custom_fields": {},
            "count_prefixes": 108,
            "count_vlans": 46,
            "count_racks": 8,
            "count_devices": 254,
            "count_circuits": 6
        },
        ...
    ]
}
```

### Retrieving a single site by ID

Send a `GET` request to the object detail endpoint. The response contains a single JSON object.

```
$ curl -H "Accept: application/json; indent=4" http://localhost/api/dcim/sites/6/
{
    "id": 6,
    "name": "Corporate HQ",
    "slug": "corporate-hq",
    "region": null,
    "tenant": null,
    "facility": "",
    "asn": null,
    "physical_address": "742 Evergreen Terrace, Springfield, USA",
    "shipping_address": "",
    "contact_name": "",
    "contact_phone": "",
    "contact_email": "",
    "comments": "",
    "custom_fields": {},
    "count_prefixes": 108,
    "count_vlans": 46,
    "count_racks": 8,
    "count_devices": 254,
    "count_circuits": 6
}
```

### Creating a new site

Send a `POST` request to the site list endpoint with token authentication and JSON-formatted data. Only mandatory fields are required.

```
$ curl -X POST -H "Authorization: Token d2f763479f703d80de0ec15254237bc651f9cdc0" -H "Content-Type: application/json" -H "Accept: application/json; indent=4" http://localhost:8000/api/dcim/sites/ --data '{"name": "My New Site", "slug": "my-new-site"}'
{
    "id": 16,
    "name": "My New Site",
    "slug": "my-new-site",
    "region": null,
    "tenant": null,
    "facility": "",
    "asn": null,
    "physical_address": "",
    "shipping_address": "",
    "contact_name": "",
    "contact_phone": "",
    "contact_email": "",
    "comments": ""
}
```

### Modify an existing site

Make an authenticated `PUT` request to the site detail endpoint. As with a create (POST) request, all mandatory fields must be included.

```
$ curl -X PUT -H "Authorization: Token d2f763479f703d80de0ec15254237bc651f9cdc0" -H "Content-Type: application/json" -H "Accept: application/json; indent=4" http://localhost:8000/api/dcim/sites/16/ --data '{"name": "Renamed Site", "slug": "renamed-site"}'
```

### Delete an existing site

Send an authenticated `DELETE` request to the site detail endpoint.

```
$ curl -v X DELETE -H "Authorization: Token d2f763479f703d80de0ec15254237bc651f9cdc0" -H "Content-Type: application/json" -H "Accept: application/json; indent=4" http://localhost:8000/api/dcim/sites/16/
* Connected to localhost (127.0.0.1) port 8000 (#0)
> DELETE /api/dcim/sites/16/ HTTP/1.1
> User-Agent: curl/7.35.0
> Host: localhost:8000
> Authorization: Token d2f763479f703d80de0ec15254237bc651f9cdc0
> Content-Type: application/json
> Accept: application/json; indent=4
>
* HTTP 1.0, assume close after body
< HTTP/1.0 204 No Content
< Date: Mon, 20 Mar 2017 16:13:08 GMT
< Server: WSGIServer/0.1 Python/2.7.6
< Vary: Accept, Cookie
< X-Frame-Options: SAMEORIGIN
< Allow: GET, PUT, PATCH, DELETE, OPTIONS
<
* Closing connection 0
```

The response to a successfull `DELETE` request will have code 204 (No Content); the body of the response will be empty.
