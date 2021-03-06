var URLS = {
    'heartbeat': '/api/heartbeat/',
    'species': '/api/species/',
    'magnifications': '/api/magnifications/',
    'development_stages': '/api/development-stages/',
    'probes': '/api/probes/',
    'images': '/api/images/',
    'classify': '/api/classify/',
    'subregions': '/api/subregions/',
    'image_sets': '/api/image-sets/',
    'anatomy_probe_map': '/api/anatomy-probe-map/',
    'train_model': '/api/train-model/'
};

var service = angular.module('IHCApp');

service.factory(
    'Heartbeat',
    function ($resource) {
        return $resource(
            URLS.heartbeat,
            {},
            {}
        );
    }
).factory(
    'Species',
    function ($resource) {
        return $resource(
            URLS.species,
            {},
            {}
        );
    }
).factory(
    'Magnification',
    function ($resource) {
        return $resource(
            URLS.magnifications,
            {},
            {}
        );
    }
).factory(
    'DevelopmentStage',
    function ($resource) {
        return $resource(
            URLS.development_stages,
            {},
            {}
        );
    }
).factory(
    'ImageSet',
    function ($resource) {
        return $resource(
            URLS.image_sets + ':image_set_id',
            {},
            {}
        );
    }
).factory(
    'Probe',
    function ($resource) {
        return $resource(
            URLS.probes,
            {},
            {}
        );
    }
).factory(
    'AnatomyProbeMap',
    function ($resource) {
        return $resource(
            URLS.anatomy_probe_map,
            {},
            {}
        );
    }
).factory('Classify',
    function($resource) {
        return $resource(
            URLS.classify,
            {},
            {}
        );
    }
).factory(
    'Subregion',
    function($resource) {
        return $resource(
            URLS.subregions + ':id',
            {},
            {
                save: {
                    method: 'POST',
                    isArray: true
                }
            }
        );
    }
).factory(
    'Image',
    function ($resource) {
        return  $resource(
            URLS.images + ':id',
            {},
            {}
        );
    }
).factory(
    'TrainModel',
    function ($resource) {
        return  $resource(
            URLS.train_model + ':id',
            {},
            {}
        );
    }
);
