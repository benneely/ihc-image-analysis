app.controller(
    'MainController',
    [
        '$scope',
        function ($scope) {
            // placeholder
        }
    ]
);

app.controller(
    'ExperimentListController',
    [
        '$scope',
        '$q',
        'LungMapExperiment',
        'Experiment',
        function ($scope, $q, LungMapExperiment, Experiment) {
            var lm_experiments = LungMapExperiment.query({});
            var experiments = Experiment.query({});

            // wait for both experiment lists to resolve,
            // then build combined list
            $q.all([
                lm_experiments.$promise,
                experiments.$promise
            ]).then(function (results) {
                $scope.all_experiments = {};

                results[0].forEach(function(exp) {
                    $scope.all_experiments[exp] = {
                        'retrieved': false
                    }
                });

                results[1].forEach(function(exp) {
                    if ($scope.all_experiments.hasOwnProperty(exp.experiment_id)) {
                        $scope.all_experiments[exp.experiment_id].retrieved = true;
                    }
                });

                console.log('adf');
            });
        }
    ]
);