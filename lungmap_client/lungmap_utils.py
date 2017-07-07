# noinspection PyPackageRequirements
import cv2
from dateutil import parser
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from lungmap_client import lungmap_sparql_queries as sparql_queries
from SPARQLWrapper import SPARQLWrapper, JSON
import boto3
import hashlib
import os
# noinspection PyPackageRequirements
from PIL import Image
import tempfile
import warnings


lungmap_sparql_server = "http://data.lungmap.net/sparql"


session = boto3.Session(profile_name='lungmap')
s3 = session.resource('s3')
bucket = s3.Bucket('lungmap-breath-data')


def list_all_lungmap_experiments():
    """
    Call out to the LM mothership (via SPARQL) to get a list of all experiments 
    that have an image. NOTE: this could mean a .tif image or .png image 
    (or something else). No restriction is placed on the type of image.
    :return: status of sparql query
    """
    try:
        sparql = SPARQLWrapper(lungmap_sparql_server)
        sparql.setQuery(sparql_queries.ALL_EXPERIMENTS_WITH_IMAGE)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        output = []
        for x in results['results']['bindings']:
            output.append(x['experiment']['value'].split('#')[1])
        return output
    except ValueError as e:
        raise e


def _get_by_experiment(query, experiment_id):
    """
    Query LM mothership (via SPARQL) and get information by a given 
    experiment_id for a particular experiment
    :param query: a predefined query string from lungmap_client that 
    has the replacement string EXPERIMENT_PLACEHOLDER
    :param experiment_id: valid experiment_id from lungmap
    :return:
    """
    try:
        query_sub = query.replace('EXPERIMENT_PLACEHOLDER', experiment_id)
        sparql = SPARQLWrapper(lungmap_sparql_server)
        sparql.setQuery(query_sub)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        return results['results']['bindings']
    except ValueError as e:
        raise e


def get_experiment_model_data(experiment_id):
    """
    Combines three lungmap_sparql_utils functions to provide data to the 
    Experiment model via dict
    :param experiment_id: str: lungmap id
    :return: dict that matches the columns in the Experiment model
    """
    types = get_experiment_type_by_experiment(experiment_id)
    sample = get_sample_by_experiment(experiment_id)
    result = {**types, **sample, **{"experiment_id": experiment_id}}
    return result


def get_sample_by_experiment(experiment_id):
    results = _get_by_experiment(
        sparql_queries.GET_SAMPLE_BY_EXPERIMENT,
        experiment_id
    )
    if len(results) > 1:
        warnings.warn('>1 sample received, only passing first result')
    try:
        for x in results[:1]:
            row = {
                'age_label': x['age_label']['value'],
                'sex': x['sex']['value'].lower(),
                'organism_label': x['organism_label']['value'],
                'local_id': x['local_id']['value']
            }
            return row
    except ValueError as e:
        raise e


def get_images_by_experiment(experiment_id):
    results = _get_by_experiment(
        sparql_queries.GET_IMAGES_BY_EXPERIMENT,
        experiment_id
    )
    output = []
    try:
        for x in results:
            row = {}
            filename = x['img_file']['value']
            name, ext = os.path.splitext(filename)
            root = x['experiment']['value'].split('owl#')[1]
            s3_obj_key = os.path.join(root, name, filename)
            row['file_ext'] = ext
            row['image_name'] = filename
            row['image_id'] = x['image']['value'].split('owl#')[1]
            row['s3key'] = s3_obj_key
            row['experiment_id'] = root
            row['magnification'] = x['magnification']['value']
            row['x_scaling'] = x['x_scaling']['value']
            row['y_scaling'] = x['y_scaling']['value']
            output.append(row)
        return output
    except ValueError as e:
        raise e


def get_probes_by_experiment(experiment_id):
    results = _get_by_experiment(
        sparql_queries.GET_PROBE_BY_EXPERIMENT,
        experiment_id
    )
    output = []
    try:
        for x in results:
            row = {
                'color': x['color']['value'],
                'probe_label': x['probe_label']['value']
            }
            output.append(row)
        return output
    except ValueError as e:
        raise e


def get_experiment_type_by_experiment(experiment_id):
    results = _get_by_experiment(
        sparql_queries.GET_EXPERIMENT_TYPE_BY_EXPERIMENT,
        experiment_id
    )

    if len(results) > 1:
        raise ValueError(
            'too many results'
        )
    if len(results) == 0:
        raise ValueError(
            'no results found'
        )
    try:
        for x in results:
            row = {
                'platform': x['platform']['value'],
                'release_date': parser.parse(
                    x['release_date']['value']
                ).strftime('%Y-%m-%d'),
                'experiment_type_label': x['experiment_type_label']['value']
            }
        return row
    except ValueError as e:
        raise e


def get_researcher_by_experiment(experiment_id):
    results = _get_by_experiment(
        sparql_queries.GET_RESEARCHER_BY_EXPERIMENT,
        experiment_id
    )
    if len(results) > 1:
        raise ValueError(
            'too many results'
        )
    try:
        for x in results:
            row = {
                'researcher_label': x['researcher_label']['value'],
                'site_label': x['site_label']['value']
            }
        return row
    except ValueError as e:
        raise e


def get_image_from_s3(s3key):
    """
    Takes an s3key and then downloads the image, calculates a SHA1, 
    creates a SimpleUploadedFile, converts to jpeg
    and then creates another SimpleUploadedFile for the jpeg, 
    returns 3 objects
    :param s3key: 
    :return: SimpleUploadedFile (orig), SHA1 Hash (orig), 
    SimpleUploadedFile (jpeg converted)
    """
    try:
        s3key_jpg, ext = os.path.splitext(s3key)
        temp = tempfile.NamedTemporaryFile(suffix=ext)
        bucket.download_file(s3key, temp.name)
        # noinspection PyUnresolvedReferences
        cv_img = cv2.imread(temp.name)
        # noinspection PyUnresolvedReferences
        img = Image.fromarray(
            cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB),
            'RGB'
        )
        img_jpeg = img.copy()
        temp_handle = BytesIO()
        img.save(temp_handle, 'TIFF')
        temp_handle.seek(0)

        # jpeg image
        temp_handle_jpeg = BytesIO()
        img_jpeg.save(temp_handle_jpeg, 'JPEG')
        temp_handle_jpeg.seek(0)

        # filename
        suf = SimpleUploadedFile(
            os.path.basename(s3key),
            temp_handle.read(),
            content_type='image/tif'
        )
        suf_jpg = SimpleUploadedFile(
            os.path.basename(s3key_jpg) + '.jpg',
            temp_handle_jpeg.read(),
            content_type='image/jpeg'
        )

        temp_handle.seek(0)
        image_orig_sha1 = hashlib.sha1(temp_handle.read()).hexdigest()

        return suf, image_orig_sha1, suf_jpg
    except ValueError as e:
        raise e
