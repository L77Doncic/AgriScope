# -*- coding: utf-8 -*-
import os
from pathlib import Path
import logging

import pandas as pd
import numpy as np

from catboost import CatBoostRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    r2_score,
    mean_squared_error,
    mean_absolute_percentage_error,
    mean_absolute_error,
)

# Optional imports
try:
    from bayes_opt import BayesianOptimization
except Exception:
    BayesianOptimization = None

try:
    import shap
    import matplotlib.pyplot as plt
except Exception:
    shap = None
    plt = None


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    return df


def split_xy(df: pd.DataFrame, test_size: float = 0.25, random_state: int = 42):
    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]
    return train_test_split(X, y, test_size=test_size, random_state=random_state)


def train_baseline(X_train, X_test, y_train, y_test, output_dir: Path, params=None):
    params = params or {
        'learning_rate': 0.1,
        'depth': 6,
        'iterations': 1000,
        'eval_metric': 'RMSE',
        'random_state': 42,
    }
    model = CatBoostRegressor(**params)
    model.fit(X_train, y_train, eval_set=(X_test, y_test), use_best_model=True, verbose=100)

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = mean_absolute_percentage_error(y_test, y_pred)
    rae = mean_absolute_error(y_test, y_pred) / np.mean(np.abs(y_test - np.mean(y_test)))

    logging.info('Baseline results: R2=%.4f RMSE=%.4f MAPE=%.4f RAE=%.4f', r2, rmse, mape, rae)

    preds = pd.DataFrame({'Actual': y_test, 'Predicted': y_pred}, index=X_test.index)
    preds.to_csv(output_dir / 'baseline_predictions.csv')

    return model


def bayes_optimize(X_train, X_test, y_train, y_test, output_dir: Path, init_points=5, n_iter=25):
    if BayesianOptimization is None:
        raise RuntimeError('bayes_opt not installed. Install with `pip install bayesian-optimization`.')

    def catboost_cv(learning_rate, depth, l2_leaf_reg, border_count, iterations):
        model = CatBoostRegressor(
            learning_rate=learning_rate,
            depth=int(depth),
            l2_leaf_reg=l2_leaf_reg,
            border_count=int(border_count),
            iterations=int(iterations),
            eval_metric='RMSE',
            random_seed=42,
            verbose=0,
        )
        model.fit(X_train, y_train, eval_set=(X_test, y_test), use_best_model=True, verbose=False)
        y_pred = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        return -rmse

    pbounds = {
        'learning_rate': (0.01, 0.5),
        'depth': (3, 16),
        'l2_leaf_reg': (1, 20),
        'border_count': (32, 255),
        'iterations': (100, 1000),
    }

    optimizer = BayesianOptimization(f=catboost_cv, pbounds=pbounds, random_state=42)
    optimizer.maximize(init_points=init_points, n_iter=n_iter)

    best_params = optimizer.max['params']
    model = CatBoostRegressor(
        learning_rate=best_params['learning_rate'],
        depth=int(best_params['depth']),
        l2_leaf_reg=best_params['l2_leaf_reg'],
        border_count=int(best_params['border_count']),
        iterations=int(best_params['iterations']),
        eval_metric='RMSE',
        random_seed=42,
        verbose=100,
    )

    model.fit(X_train, y_train, eval_set=(X_test, y_test), use_best_model=True, verbose=True)

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = mean_absolute_percentage_error(y_test, y_pred)
    rae = mean_absolute_error(y_test, y_pred) / np.mean(np.abs(y_test - np.mean(y_test)))

    logging.info('Bayes-opt results: R2=%.4f RMSE=%.4f MAPE=%.4f RAE=%.4f', r2, rmse, mape, rae)

    with open(output_dir / 'bayes_best_params.txt', 'w') as f:
        f.write(str(optimizer.max))

    return optimizer, model


def shap_analysis(model: CatBoostRegressor, X_test: pd.DataFrame, output_dir: Path):
    if shap is None or plt is None:
        raise RuntimeError('shap or matplotlib not installed. Install with `pip install shap matplotlib`.')

    explainer = shap.Explainer(model)
    shap_values = explainer(X_test)

    shap_values_df = pd.DataFrame(shap_values.values, columns=X_test.columns)
    shap_values_df.to_csv(output_dir / 'KUIHUAshap_values.csv', index=False)

    mean_shap_values = np.mean(np.abs(shap_values.values), axis=0)
    mean_shap_df = pd.DataFrame({'Feature': X_test.columns, 'Mean |SHAP value|': mean_shap_values})
    mean_shap_df.to_csv(output_dir / 'KUIHUAmean_shap_values.csv', index=False)

    plt.figure(figsize=(14, 10))
    shap.summary_plot(shap_values, X_test, show=False, max_display=X_test.shape[1])
    plt.savefig(output_dir / 'KUIHUAshap_summary_plot.png')
    plt.close()

    plt.figure(figsize=(14, 10))
    mean_shap_df.sort_values(by='Mean |SHAP value|', ascending=False).plot.bar(x='Feature', y='Mean |SHAP value|', legend=False)
    plt.title('Mean |SHAP value| for all features')
    plt.ylabel('Mean |SHAP value|')
    plt.xlabel('Feature')
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig(output_dir / 'KUIHUAmean_shap_values_plot.png')
    plt.close()

    shap_values_array = shap_values.values if hasattr(shap_values, 'values') else shap_values
    logging.info('SHAP values shape: %s, X_test shape: %s', getattr(shap_values_array, 'shape', None), X_test.shape)

    for feature in ['AT', 'CS', 'SEC', 'IW', 'MinT']:
        try:
            plt.figure(figsize=(14, 10))
            shap.dependence_plot(feature, shap_values_array, X_test, interaction_index='auto')
            plt.title(f'Partial Dependence Plot for {feature} with Interaction')
            plt.savefig(output_dir / f'{feature}_partial_dependence_plot_with_interaction.png')
            plt.close()
        except Exception:
            logging.warning('Could not create dependence plot for feature %s', feature)


def scenario_simulation(optimizer, s5_path: str, output_dir: Path):
    df = load_data(s5_path)
    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]
    n = len(df)
    test_size = 8 * n // 14
    train_size = n - test_size

    X_train = X.iloc[:train_size]
    y_train = y.iloc[:train_size]
    X_test = X.iloc[train_size:]
    y_test = y.iloc[train_size:]

    if optimizer is None:
        raise RuntimeError('optimizer required for scenario simulation (must run bayes first)')

    best_params = optimizer.max['params']
    model = CatBoostRegressor(
        learning_rate=best_params['learning_rate'],
        depth=int(best_params['depth']),
        l2_leaf_reg=best_params['l2_leaf_reg'],
        border_count=int(best_params['border_count']),
        iterations=int(best_params['iterations']),
        eval_metric='RMSE',
        random_seed=42,
        verbose=100,
    )

    model.fit(X_train, y_train, eval_set=(X_test, y_test), use_best_model=True, verbose=True)
    y_pred = model.predict(X_test)

    predictions = pd.DataFrame({'Actual': y_test, 'Predicted': y_pred}, index=X_test.index)
    predictions.to_csv(output_dir / 'KUIHUA_S5_predictions.csv')

    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = mean_absolute_percentage_error(y_test, y_pred)
    rae = mean_absolute_error(y_test, y_pred) / np.mean(np.abs(y_test - np.mean(y_test)))

    logging.info('Scenario results: R2=%.4f RMSE=%.4f MAPE=%.4f RAE=%.4f', r2, rmse, mape, rae)

    return model


def main():

    INPUT_PATH = "KUIHUAWP.xlsx"          
    INPUT_S5_PATH = "KUIHUAWP.xlsx"       
    OUTPUT_DIR = Path("output")           
    MODEL_SAVE_PATH = OUTPUT_DIR / "best_catboost_model.cbm"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    # 加载主数据
    df = load_data(INPUT_PATH)
    logging.info('Loaded main data shape: %s', df.shape)

    X_train, X_test, y_train, y_test = split_xy(df)

    optimizer = None
    best_model = None

    # Step 1: Baseline
    logging.info('Running baseline training...')
    best_model = train_baseline(X_train, X_test, y_train, y_test, OUTPUT_DIR)

    # Step 2: Bayesian Optimization
    logging.info('Running Bayesian optimization...')
    optimizer, best_model = bayes_optimize(X_train, X_test, y_train, y_test, OUTPUT_DIR)

    # Step 3: SHAP Analysis
    logging.info('Running SHAP analysis...')
    try:
        shap_analysis(best_model, X_test, OUTPUT_DIR)
    except RuntimeError as e:
        logging.error("SHAP error: %s", str(e))

    # Step 4: Scenario Simulation (using INPUT_S5_PATH)
    logging.info('Running scenario simulation...')
    try:
        scenario_model = scenario_simulation(optimizer, INPUT_S5_PATH, OUTPUT_DIR)
        # 保存场景模型（可选）
        scenario_model.save_model(OUTPUT_DIR / "scenario_catboost_model.cbm")
    except Exception as e:
        logging.error("Scenario simulation failed: %s", str(e))

    # 保存贝叶斯优化后最佳模型的预测结果（主测试集）
    logging.info('Saving predictions from the best (Bayes-optimized) model...')
    y_pred_best = best_model.predict(X_test)
    best_preds_df = pd.DataFrame({
        'Actual': y_test,
        'Predicted': y_pred_best
    }, index=X_test.index)
    best_preds_df.to_csv(OUTPUT_DIR / 'best_model_predictions.csv')
    logging.info('Best model predictions saved to: %s', OUTPUT_DIR / 'best_model_predictions.csv')

    # 保存主流程最优模型
    best_model.save_model(MODEL_SAVE_PATH)
    logging.info(f"Best model saved to: {MODEL_SAVE_PATH}")


if __name__ == '__main__':
    main()
