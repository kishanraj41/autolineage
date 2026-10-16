import numpy as np

import pandas as pd

from sklearn.datasets import fetch_openml

from sklearn.model_selection import train_test_split, cross_val_score

from sklearn.metrics import accuracy_score

from sklearn.preprocessing import StandardScaler, OneHotEncoder

from sklearn.compose import ColumnTransformer

from sklearn.svm import SVC

import matplotlib.pyplot as plt

from typing import List, Tuple



def rbf_kernel(x: np.ndarray, c: np.ndarray, gamma: float = 0.1) -> float:

    return np.exp(-gamma * np.linalg.norm(x - c) ** 2)



def initial_projection(X: np.ndarray, centroids: np.ndarray, gamma: float = 0.1) -> np.ndarray:

    # Project the input data X onto the space defined by centroids using the RBF kernel

    return np.array([[rbf_kernel(x, c, gamma) for c in centroids] for x in X])



class WLS_SVC:

    def __init__(self, C: float = 1.0, max_iter: int = 10, tol: float = 1e-3, learning_rate: float = 0.01):

        self.C = C

        self.max_iter = max_iter

        self.tol = tol

        self.learning_rate = learning_rate

    

    def fit(self, X_proj: np.ndarray, y: np.ndarray) -> None:

        l, M = X_proj.shape

        self.w = np.zeros(M)

        self.b = 0

        y = y.astype(np.float64)

        

        for iteration in range(self.max_iter):

            current_lr = self.learning_rate / (1 + 0.01 * iteration)  # adaptive learning rate

            margins = y * (np.dot(X_proj, self.w) + self.b)

            loss = 1 - margins

            loss[loss < 1] = 0  # Only hinge loss

            

            grad_w = self.w - self.C * np.dot((loss > 0) * y, X_proj) / l

            grad_b = -self.C * np.mean((loss > 0) * y)

            

            if np.linalg.norm(grad_w) < self.tol and abs(grad_b) < self.tol:

                break 

            

            self.w -= current_lr * grad_w

            self.b -= current_lr * grad_b

    

    def predict(self, X: np.ndarray) -> np.ndarray:

        return np.sign(np.dot(X, self.w) + self.b).astype(int)



def find_new_centroids(X: np.ndarray, y: np.ndarray, model: WLS_SVC, centroids: np.ndarray, gamma: float = 0.1, num_new_centroids: int = 2) -> np.ndarray:

    # Identify new centroids based on support vectors and their distance from existing centroids

    X_proj = initial_projection(X, centroids, gamma)

    margins = y * (np.dot(X_proj, model.w) + model.b)

    

    # select support vectors close to the decision boundary

    support_vectors = X[(margins > 0) & (margins < 1)]

    if len(support_vectors) == 0:

        return np.array([]) 

    

    # distances from support vectors to existing centroids

    distances = np.array([np.min([np.linalg.norm(sv - c) for c in centroids]) for sv in support_vectors])

    

    # farthest support vectors as new centroids

    farthest_indices = np.argsort(distances)[::-1]

    farthest_support_vectors = support_vectors[farthest_indices]

    

    return farthest_support_vectors[:num_new_centroids]



def select_initial_centroids(X: np.ndarray, y: np.ndarray, M: int = 2) -> np.ndarray:

    # initial centroids are picked randomly

    unique_classes = np.unique(y)

    centroids = []

    

    for cls in unique_classes:

        class_samples = X[y == cls]

        selected_centroids = class_samples[np.random.choice(class_samples.shape[0], max(1, M // 2), replace=False)]

        centroids.append(selected_centroids)

    

    return np.vstack(centroids)



def iterative_poker(X, y, initial_centroids, max_iterations=10, gamma=0.1, patience=3):

    centroids = initial_centroids

    wls_svc = WLS_SVC(C=1.0, learning_rate=0.01, max_iter=10, tol=1e-3)

    

    accuracy_history = []

    num_centroids_history = [len(centroids)]

    best_accuracy = 0

    no_improvement_counter = 0

    

    for iteration in range(max_iterations):

        projection = initial_projection(X, centroids, gamma)

        wls_svc.fit(projection, y)

        

        poker_predictions = wls_svc.predict(projection)

        poker_accuracy = accuracy_score(y, poker_predictions)

        accuracy_history.append(poker_accuracy)

        

        if poker_accuracy > best_accuracy:

            best_accuracy = poker_accuracy

            no_improvement_counter = 0

        else:

            no_improvement_counter += 1

        

        if no_improvement_counter >= patience:

            print(f"No improvement for {patience} iterations, stopping.")

            break

        

        # find new centroids and add them to the existing ones

        new_centroids = find_new_centroids(X, y, wls_svc, centroids, gamma, num_new_centroids=2)

        if len(new_centroids) == 0:

            print(f"No new centroids found after {iteration + 1} iterations")

            break

        

        centroids = np.vstack([centroids, new_centroids])

        num_centroids_history.append(len(centroids))

        print(f"Iteration {iteration + 1}: Accuracy = {poker_accuracy}, Centroids = {len(centroids)}")

    

    return wls_svc, centroids, accuracy_history, num_centroids_history



def plot_results(accuracy_history: List[float], num_centroids_history: List[int], svm_accuracy: float) -> None:

    iterations = range(1, len(accuracy_history) + 1)

    

    plt.figure(figsize=(12, 6))

    

    # plot accuracy

    plt.subplot(1, 2, 1)

    plt.plot(iterations, accuracy_history, marker='o', color='b', label='POKER Accuracy')

    plt.axhline(y=svm_accuracy, color='g', linestyle='--', label='Linear SVM Accuracy')

    plt.xlabel('Iteration')

    plt.ylabel('Accuracy')

    plt.title('Accuracy Over Iterations')

    plt.legend()

    

    # plot number of centroids

    plt.subplot(1, 2, 2)

    plt.plot(iterations, num_centroids_history, marker='o', color='r', label='Number of Centroids')

    plt.xlabel('Iteration')

    plt.ylabel('Number of Centroids')

    plt.title('Number of Centroids Over Iterations')

    plt.legend()

    

    plt.tight_layout()

    plt.show()



datasets = {

    'abalone': ('abalone', 'Class_number_of_rings'),

    'image': ('segment', 'class'),

    'pima': ('diabetes', 'class'),

    'waveform': ('waveform-5000', 'class')

}



results_list = []



for dataset_name, (data_name, target_name) in datasets.items():

    print(f"Processing dataset: {dataset_name}")

    

    try:

        data = fetch_openml(name=data_name, version=1, as_frame=True, parser='auto')

        X, y = data.data, data.target

        

        # convert to binary if needed

        # change this

        if dataset_name in ['abalone', 'image', 'waveform']:

            y = (y == y.unique()[0]).astype(int) * 2 - 1

        

        # preprocessing

        numeric_features = X.select_dtypes(include=[np.number]).columns.tolist()

        categorical_features = X.select_dtypes(include=[object]).columns.tolist()

        

        preprocessor = ColumnTransformer(

            transformers=[

                ('num', StandardScaler(), numeric_features),

                ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)

            ]

        )

        

        X = preprocessor.fit_transform(X)

        

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

        

        # linear SVM for comparison

        linear_svm = SVC(kernel='linear', C=1.0)

        linear_svm.fit(X_train, y_train)

        svm_predictions = linear_svm.predict(X_test)

        svm_accuracy = accuracy_score(y_test, svm_predictions)

        

        M_list = [1, 2, 4, 8]

        for M in M_list:

            initial_centroids = select_initial_centroids(X_train, y_train, M=M)

            

            poker_model, final_centroids, accuracies, centroids_count = iterative_poker(

                X_train, y_train, initial_centroids, gamma=0.1

            )

            

            plot_results(accuracies, centroids_count, svm_accuracy)

            

            poker_projection = initial_projection(X_test, final_centroids, gamma=0.1)

            poker_predictions = poker_model.predict(poker_projection)

            poker_accuracy = accuracy_score(y_test, poker_predictions)

            

            results_list.append({

                'Dataset': dataset_name,

                'M': M,

                'POKER Accuracy': poker_accuracy,

                'Linear SVM Accuracy': svm_accuracy

            })

            print(f"M: {M}, POKER Accuracy: {poker_accuracy}, Linear SVM Accuracy: {svm_accuracy}")

    except Exception as e:

        print(f"Error processing dataset {dataset_name}: {e}")



results_df = pd.DataFrame(results_list)

print(results_df)

