import numpy as np
from sklearn import linear_model
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler, PolynomialFeatures
import pandas as pd
import shutil
# import the os module
import os
from glob import glob
from yellowbrick.regressor import *
from yellowbrick.model_selection import LearningCurve, ValidationCurve, RFECV, FeatureImportances
import logging
import sys
from sklearn.metrics import make_scorer, mean_squared_error
import shap
import matplotlib.pyplot as plt
from sklearn.inspection import permutation_importance


def setup_data(path):
    dataset = pd.read_csv(path)

    missing = pd.DataFrame(dataset.isnull().sum(), columns=['Total'])
    missing['%'] = (missing['Total'] / dataset.shape[0]) * 100
    missing.sort_values(by='%', ascending=False)

    size = dataset.shape[0]
    dataset = dataset.dropna()

    print('Number of rows in the dataset after the rows with missing values were removed: {}.\n{} rows were removed.'
          .format(dataset.shape[0], size - dataset.shape[0]))

    # Remove Severe Outliers
    cols = ['bmdtest_height', 'bmdtest_weight']

    for c in cols:
        upper_level = dataset[c].mean() + 3 * dataset[c].std()
        lower_level = dataset[c].mean() - 3 * dataset[c].std()
        dataset = dataset[(dataset[c] > lower_level) & (dataset[c] < upper_level)]

    print('Number of rows in the dataset after the rows with missing values were removed: {}.\n{} rows were removed.'
          .format(dataset.shape[0], size - dataset.shape[0]))

    # Reset the Index
    dataset.reset_index(drop=True, inplace=True)

    # Drop the PatientID column as it is no longer needed
    # dataset.drop(['PatientId'], axis=1, inplace=True)

    dataset.drop(dataset.index[dataset['ankle'] == 1], inplace=True)

    print('Number of rows in the dataset after the rows with ankle were removed: {}.\n{} rows were removed.'
          .format(dataset.shape[0], size - dataset.shape[0]))
    # Create the dataset that will be used to train the models
    # and the data that will be used to perform the predictions to test the models

    dataset.reset_index(drop=True, inplace=True)

    print('Data for Modeling: ' + str(dataset.shape))

    return dataset


def create_model():
    lr = linear_model.LinearRegression()

    return lr


def encode_cat_data(data):
    cat_features = ['parentbreak', 'alcohol',
                    # 'arthritis', 'cancer', 'diabetes', 'heartdisease',
                    # 'oralster', 'smoke', 'respdisease',
                    'ptunsteady', 'wasfractdue2fall',
                    'ptfall', 'ankle', 'clavicle', 'shoulder', 'elbow', 'femur', 'wrist', 'tibfib']
    dataset = data.copy()

    for feature in cat_features:
        cat_one_hot = pd.get_dummies(dataset[feature], prefix=f'pt_response_{feature}', drop_first=True)
        dataset = dataset.drop(feature, axis=1)
        dataset = dataset.join(cat_one_hot)

    return dataset


def scale_data(x_train, scaler):
    cols_to_scale = ['PatientAge', 'bmi']
    scaler.fit(x_train[cols_to_scale].copy())
    x_train[cols_to_scale] = scaler.transform(x_train[cols_to_scale])

    return x_train


def poly_data(x_train):
    poly = PolynomialFeatures(2, include_bias=False, interaction_only=True)

    x_train = pd.DataFrame(poly.fit_transform(x_train),
                           columns=['PatientAge', 'PatientGender', 'bmi', 'Age*Gender', 'Age*bmi', 'Gender*bmi'])
    x_train.drop(['PatientAge', 'PatientGender', 'bmi'], axis=1, inplace=True)

    return x_train


def evaluate_model(regression_model, train_data, X_te, y_te, predictions):
    coefs = []
    for i in range(train_data.shape[1]):
        coefs.append(f'{train_data.columns[i]}' + '=' + f'{regression_model.coef_[i].round(4)}')
    logging.info(
        f"Saving Results for {regression_model} to SciKit_Model_Results.txt")
    with open('SciKit_Model_Results.txt', 'a') as result_file:
        rmse = np.sqrt(mean_squared_error(y_te, predictions))
        result_file.write(
            f"\nModel {regression_model}\n\nHyper Parameters: \n{regression_model.get_params()}\n"
            f"RMSE for Model {regression_model}: \n" +
            f"Root Mean Squared Error: {rmse} \n"
        )
        result_file.write(
            f"R2 for Model {regression_model}:\n" +
            f"R^2: {regression_model.score(X_te, y_te)} \n\n"
        )
        result_file.write(
            "Model Coefficients:\n"
        )
        for coef in coefs:
            result_file.writelines(coef + '\n')


def get_object_type(obj):
    return type(obj)


def plot_results(regression_model, x_tr, y_tr, x_te, y_te, model_no):
    """A function that takes in the top 3 models produced by PyCaret and plots the results and saves them to the
    models_results directory """
    current_dir = os.getcwd()
    dst_dir = current_dir + "/Output/models_results"
    plot_types = ['residuals', 'error', 'learning', 'vc', 'feature', 'cooks', 'rfe', 'permutation']

    try:
        # Create plots for the model
        for plot in plot_types:
            try:
                if plot == 'residuals':
                    visualizer = ResidualsPlot(regression_model)
                    visualizer.fit(x_tr, y_tr)
                    visualizer.score(x_te, y_te)
                    visualizer.show(outpath=f"model{model_no + 1}_residuals.png", clear_figure=True)

                elif plot == 'error':
                    visualizer = PredictionError(regression_model)
                    visualizer.fit(x_tr, y_tr)
                    visualizer.score(x_te, y_te)
                    visualizer.show(outpath=f"model{model_no + 1}_prediction_error.png", clear_figure=True)

                elif plot == 'learning':
                    visualizer = LearningCurve(regression_model, scoring='r2', param_name='Training Instances',
                                               param_range=np.arange(1, 800))
                    visualizer.fit(x_tr, y_tr)
                    visualizer.show(outpath=f"model{model_no + 1}_learning_curve.png", clear_figure=True)

                elif plot == 'feature':
                    visualizer = FeatureImportances(regression_model, relative=False)
                    visualizer.fit(x_tr, y_tr)
                    visualizer.show(outpath=f"model{model_no + 1}_feature_importance.png", clear_figure=True)

                elif plot == 'cooks':
                    visualizer = CooksDistance()
                    visualizer.fit(X, y)
                    visualizer.show(outpath=f"model{model_no + 1}_cooks_distance.png", clear_figure=True)

                elif plot == 'permutation':
                    plot_permutation_importance(regression_model, model_no + 1, x_tr, y_tr)

                else:
                    visualizer = RFECV(regression_model)
                    visualizer.fit(x_tr, y_tr)
                    visualizer.show(outpath=f"model{model_no + 1}_recursive_feature_elimination.png", clear_figure=True)

            except Exception as er:
                logging.error(er)
                logging.error(f"'{plot}' plot is not available for this model. Plotting a different graph.")

        print(f"All Plots for {regression_model} have been created Successfully")

        print(f'Moving plots for {regression_model}')

        # Move the plots to their respective models directory
        files = glob('*.png')
        if len(files) == 0:
            logging.info('There are no Plots to move.')
            return
        for file in files:

            if file.endswith('.png'):
                shutil.move(os.path.join(current_dir, file),
                            os.path.join(dst_dir + f"/scikit_model_{model_no + 1}", file))

    except Exception as er:
        logging.error(er)
        logging.error("Plot Operations were unable to be completed.")


def create_model_set(data, features, target):
    """Splits the Data into the Features you want to train and the target your model will be predicting"""
    copy = data.copy()
    feature_set = copy[features]
    target_column = copy[target]
    return feature_set, target_column


def create_shap_sample(data, num_of_instances):
    sample = shap.utils.sample(data, num_of_instances, random_state=120)
    return sample


def view_model_coefs(model, data):
    print("Model Coefficients:\n")
    for i in range(data.shape[1]):
        print(data.columns[i], '=', model.coef_[i].round(4))


def create_explainer(model, sample):
    explainer = shap.Explainer(model.predict, sample)
    return explainer


def plot_waterfall(data, explainer, model_no):
    current_dir = os.getcwd()
    female_data = data[data['PatientGender'] == 1]
    male_data = data[data['PatientGender'] == 2]
    dst_dir = current_dir + "/Output/models_results"
    sample_ind = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    female_shap_values = explainer(female_data)
    male_shap_values = explainer(male_data)

    for ind in sample_ind:
        shap.plots.waterfall(female_shap_values[ind], show=False)
        plt.tight_layout()
        plt.savefig(f'female_waterfall_sample{ind}.png', )
        plt.clf()

    for ind in sample_ind:
        shap.plots.waterfall(male_shap_values[ind], show=False)
        plt.tight_layout()
        plt.savefig(f'male_waterfall_sample{ind}.png', )
        plt.clf()

    # Move the plots to their respective models directory
    files = glob('*.png')
    if len(files) == 0:
        logging.info('There are no Plots to move.')
        return
    for file in files:
        if file.endswith('.png'):
            shutil.move(os.path.join(current_dir, file),
                        os.path.join(dst_dir + f"/scikit_model_{model_no + 1}" + '/waterfalls', file))


def plot_summary(explainer, data, feature_names):
    shap_values = explainer(data)
    shap.summary_plot(shap_values, X_test, feature_names=feature_names, show=False)
    plt.tight_layout()
    plt.savefig(f'shap_summary.png', )
    plt.clf()


def plot_permutation_importance(model, name, X, y):

    result = permutation_importance(model, X, y, n_repeats=50, scoring=make_scorer(mean_squared_error))
    sorted_importances_idx = result.importances_mean.argsort()

    importance = pd.DataFrame(result.importances.T, columns=X.columns)
    importance.to_csv(f'model{name}_permutation_importance.csv')

    plt.barh(X.columns[sorted_importances_idx], result.importances_mean[sorted_importances_idx].T)
    plt.xlabel('Permutation Importance')
    plt.savefig(f'model{name}_permutation_importance.png')


if __name__ == "__main__":
    try:
        # Get the data from the argument
        file_name = sys.argv[1]
        # file_name = '../Clean_Data_Main.csv'
        logging.info(f'Loading Data {file_name}\n')

        # Perform the analysis and generate the images
        main_data = setup_data(file_name)

    except ValueError as e:
        logging.error(e)
        logging.error('Unable to load the CSV File')

    lr = create_model()

    if main_data is not None:
        main_data = encode_cat_data(main_data)

        X, y = create_model_set(main_data,
                                ['PatientId', 'PatientAge', 'PatientGender', 'bmi', 'bmdtest_height', 'bmdtest_weight', 'pt_response_clavicle_1.0',
                                 'pt_response_shoulder_1.0',
                                 'pt_response_elbow_1.0', 'pt_response_femur_1.0', 'pt_response_wrist_1.0',
                                 'pt_response_tibfib_1.0'], 'bmdtest_tscore_fn')

        logging.info('Explanatory Features and Target columns have been created')

        poly_features = X[['PatientAge', 'PatientGender', 'bmi']]
        poly_features = poly_data(poly_features)
        logging.info('Polynomial Features have been created')

        X = pd.concat([X, poly_features], axis=1)
        logging.info('Polynomial Features have been added to the dataset')

        # Scale the Data
        scaler = StandardScaler()
        X = scale_data(X, scaler)
        logging.info('Data has been scaled')

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=786, shuffle=True)

        temp = X_test

        X_train = X_train.drop(['PatientId', 'bmdtest_weight', 'bmdtest_height'], axis=1)
        X_test = X_test.drop(['PatientId', 'bmdtest_weight', 'bmdtest_height'], axis=1)

        X100 = create_shap_sample(X_test, 100)

        model_explainer = create_explainer(lr, X100)

        lr.fit(X_train, y_train)
        view_model_coefs(lr, X_train)

        plot_waterfall(X_train, model_explainer, 1)

        y_pred = lr.predict(X_test)
        evaluate_model(lr, X_train, X_test, y_test, y_pred)
        plot_summary(model_explainer, X_test, ['PatientAge', 'PatientGender', 'bmi', 'bmdtest_height', 'bmdtest_weight', 'pt_response_clavicle_1.0',
                                               'pt_response_shoulder_1.0',
                                               'pt_response_elbow_1.0', 'pt_response_femur_1.0',
                                               'pt_response_wrist_1.0',
                                               'pt_response_tibfib_1.0', 'Age*Gender', 'Age*bmi', 'Gender*bmi'])
        plot_results(lr, X_train, y_train, X_test, y_test, 1)
        temp['predicted_t_score'] = y_pred
        temp_scaled = scaler.inverse_transform(temp[['PatientAge', 'bmi']])
        temp[['PatientAge', 'bmi']] = temp_scaled
        temp = temp.drop(['pt_response_clavicle_1.0', 'pt_response_shoulder_1.0',
                   'pt_response_elbow_1.0', 'pt_response_femur_1.0', 'pt_response_wrist_1.0',
                   'pt_response_tibfib_1.0'], axis=1)
        temp.to_csv('LR_predictions.csv')
        print('All Operations have been completed. Closing Program.')

    else:
        logging.error('No data exists.')
