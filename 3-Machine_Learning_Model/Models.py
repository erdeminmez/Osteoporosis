import logging
import sys

import numpy as np
import statistics
from collections import Counter
import pandas as pd
from scipy import stats
import seaborn as sns
import matplotlib.pyplot as plt
import shutil
# import the os module
import os
from glob import glob
from pycaret.regression import *
from pycaret.utils import check_metric


def set_directory():
    # detect the current working directory and add the sub directory
    main_path = os.getcwd()
    absolute_path = main_path + "/models_results"
    model1_path = absolute_path + "/model_1"
    model2_path = absolute_path + "/model_2"
    model3_path = absolute_path + "/model_3"
    try:
        os.mkdir(absolute_path)
        os.mkdir(model1_path)
        os.mkdir(model2_path)
        os.mkdir(model3_path)

    except OSError:
        logging.info("Creation of the directory %s failed. Folder already exists." % absolute_path)
    else:
        logging.info("Successfully created the directory %s " % absolute_path)


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

    # Reduce the amount of columns produced by the types of fractures and
    # consolidate them into two columns, fractured and fracture_type
    dataset = dataset.melt(id_vars=['PatientId', 'PatientAge', 'PatientGender', 'bmdtest_height', 'bmdtest_weight',
                                    'ptunsteady', 'parentbreak', 'howbreak', 'arthritis', 'cancer', 'diabetes',
                                    'heartdisease', 'respdisease', 'alcohol', 'bmdtest_tscore_fn'],
                           value_vars=['hip', 'ankle', 'clavicle', 'elbow', 'femur', 'spine', 'wrist',
                                       'shoulder', 'tibfib'],
                           var_name="fracture_type",
                           value_name='fractured',
                           ignore_index=False)

    # Sort dataset to ensure patients with fractures are kept after cleaning
    dataset = dataset.sort_values(by='fractured', ascending=False)

    # Clean up the duplicated patients from melting the dataset
    updated_dataset = dataset[~(dataset[['PatientId']].duplicated(keep='first'))]

    # Reset the Index
    updated_dataset.reset_index(drop=True, inplace=True)

    # Drop the PatientID column as it is no longer needed
    updated_dataset.drop(['PatientId'], axis=1, inplace=True)

    # Create the dataset that will be used to train the models
    # and the data that will be used to perform the predictions to test the models
    data = updated_dataset.sample(frac=0.9, random_state=786)
    data_unseen = updated_dataset.drop(data.index)

    data.reset_index(drop=True, inplace=True)
    data_unseen.reset_index(drop=True, inplace=True)

    print('Data for Modeling: ' + str(data.shape))
    print('Unseen Data For Predictions: ' + str(data_unseen.shape))

    return data, data_unseen


def perform_predictions(top_models):
    """
    A function that performs the predictions on the top 3 models produced by PyCaret, saves the predictions to a csv
    file per model, and saves the RMSE and R2 scores to a .txt file. It will then move these files to the
    models_results directory and their respective model_num directory.
    """
    current_dir = os.getcwd()
    dst_dir = current_dir + "/models_results"

    # Perform Predictions on the top models with the unseen data
    print('Performing Predictions on unseen data')
    predictions = [predict_model(i, unseen_data) for i in top_models]

    # Write the results to a text file and the predictions to csvs
    logging.info('Saving Results to Model_Results.txt and Predictions to csvs')
    with open('Model_Results.txt', 'w') as result_file:
        for i in range(len(top_models)):
            predictions[i].to_csv(f"Prediction_Model{i + 1}.csv")
            result_file.write(
                f'RMSE for Model {i + 1}: \n{top_models[i]}: \n' +
                f"{check_metric(predictions[i].bmdtest_tscore_fn, predictions[i].Label, 'RMSE')} \n"
            )
            result_file.write(
                f'R2 for Model {i + 1}: \n{top_models[i]}: \n' +
                f"{check_metric(predictions[i].bmdtest_tscore_fn, predictions[i].Label, 'R2')} \n"
            )

    # Move the Prediction csvs to their respective model directories
    try:
        csv_files = glob('*.csv')
        shutil.move(os.path.join(current_dir, 'Model_Results.txt'), os.path.join(dst_dir, 'Model_Results.txt'))

        for file in csv_files:
            if file.__contains__("Prediction_Model1.csv"):
                shutil.move(
                    os.path.join(current_dir, file), os.path.join(dst_dir + f"/model_1", file)
                )
            elif file.__contains__("Prediction_Model2.csv"):
                shutil.move(os.path.join(current_dir, file), os.path.join(dst_dir + f"/model_2", file))
            elif file.__contains__("Prediction_Model3.csv"):
                shutil.move(os.path.join(current_dir, file), os.path.join(dst_dir + f"/model_3", file))

        print('All Model results and predictions have been moved successfully.')
    except Exception as er:
        logging.error(er)
        logging.error("There was an error when moving the files")


def plot_results(top_models):
    """A function that takes in the top 3 models produced by PyCaret and plots the results and saves them to the
    models_results directory """
    current_dir = os.getcwd()
    dst_dir = current_dir + "/models_results"
    plot_types = ['residuals', 'error', 'learning', 'vc', 'feature', 'cooks', 'manifold', 'rfe']

    try:
        # Analyze the finalized models by saving their plots against the test data
        for i in range(len(top_models)):
            # Create plots for the top 3 models
            for plot in plot_types:
                try:
                    plot_model(top_models[i], plot=plot, save=True, plot_kwargs=dict(sorted="RMSE"))
                except Exception as er:
                    logging.error(er)
                    logging.error(f"'{plot}' plot is not available for this model. Plotting a different graph.")

            print(f"All Plots for {top_models[i]} have been created Successfully")

            print(f'Moving plots for {top_models[i]}')

            # Move the plots to their respective models directory
            files = glob('*.png')
            if len(files) == 0:
                logging.info('There are no Plots to move.')
                return
            for file in files:
                # USE THIS IF STATEMENT IF SCRIPT IS NOT RAN IN A CLEAN DIRECTORY
                # if ((file.__contains__('Cooks Distance.png')) 
                #    or (file.__contains__('Feature Importance.png')) or (file.__contains__('Feature Selection.png')) 
                #    or (file.__contains__('Learning Curve.png')) or (file.__contains__('Manifold Learning.png'))
                #    or (file.__contains__('Prediction Error.png')) or (file.__contains__('Residuals.png')) 
                #    or (file.__contains__('Validation Curve.png'))
                #    ):
                if file.endswith('.png'):
                    shutil.move(os.path.join(current_dir, file), os.path.join(dst_dir + f"/model_{i + 1}", file))

    except Exception as er:
        logging.error(er)
        logging.error("Plot Operations were unable to be completed.")


if __name__ == "__main__":
    try:
        # Get the data from the argument
        # file_name = sys.argv[1]
        file_name = '../1-Data_Cleaning/Clean_Data_Main.csv'
        logging.info(f'Loading Data {file_name}\n')

        # Create the directory where the CSV files and images are going to be saved
        set_directory()

        # Perform the analysis and generate the images
        main_data, unseen_data = setup_data(file_name)

        if main_data is not None:
            exp_name = setup(data=main_data, target='bmdtest_tscore_fn', session_id=123, train_size=0.7, fold=10,
                             categorical_features=['parentbreak', 'alcohol', 'ptunsteady'], silent=True)
            best_models = compare_models(exclude=['ransac'], sort='RMSE', n_select=3, fold=10)

            # Tune the Models
            tuned_models = [tune_model(i, optimize='RMSE', n_iter=100) for i in best_models]

            # Finalize the Model
            final_models = [finalize_model(i) for i in tuned_models]

            # Plot the Models
            plot_results(final_models)

            # Perform the Predictions
            perform_predictions(final_models)

            print('All Operations have been completed. Closing Program.')

        else:
            logging.error('No data exists.')

    except ValueError as e:
        logging.error(e)
        logging.error('Unable to load the CSV File')
