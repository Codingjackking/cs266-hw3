"""
Monte Carlo Lottery Prediction Engine with Security Enhancements
- Differential Privacy
- Data Access Logging
- Algorithm Protection
"""

import pandas as pd
import numpy as np
import os
import logging
import random

from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# LOTTERY RULES CONFIGURATION
# ============================================================================

LOTTERY_RULES = {
    "powerball": {
        "main_count": 5,
        "main_min": 1,
        "main_max": 59,  # Pre-2015 rules
        "special_name": "Powerball",
        "special_min": 1,
        "special_max": 35,  # Pre-2012 rules
        "csv_path": "powerball_results.csv"
    },
    "megamillions": {
        "main_count": 5,
        "main_min": 1,
        "main_max": 56,  # Pre-2013 rules
        "special_name": "Mega Ball",
        "special_min": 1,
        "special_max": 46,  # Pre-2013 rules
        "csv_path": "megamillions_results.csv"
    },
    "superlotto": {
        "main_count": 5,
        "main_min": 1,
        "main_max": 47,
        "special_name": "Mega",
        "special_min": 1,
        "special_max": 27,
        "csv_path": "superlotto_results.csv"
    },
    "fantasy5": {
        "main_count": 5,
        "main_min": 1,
        "main_max": 39,
        "special_name": None,  # No special ball
        "special_min": None,
        "special_max": None,
        "csv_path": "fantasy5_results.csv"
    }
}


# ============================================================================
# DATA LOADING WITH SECURITY
# ============================================================================

def load_lottery_data(lottery_type="powerball", csv_path=None, log_access=False, user_id=None):
    """
    Load and preprocess lottery data with security logging
    
    Args:
        lottery_type: Type of lottery
        csv_path: Optional path to CSV file
        log_access: Whether to log data access for audit trail
        user_id: User ID for access logging
    
    Returns:
        pandas DataFrame with historical lottery results
    """
    config = LOTTERY_RULES.get(lottery_type)
    if not config:
        raise ValueError(f"Unsupported lottery type: {lottery_type}")
    
    # SECURITY: Log data access for audit trail
    if log_access:
        logger.info(f"Historical data accessed: lottery_type={lottery_type}, user_id={user_id}, timestamp={datetime.now().isoformat()}")
    
    if csv_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(base_dir, "data", config["csv_path"])
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Parse dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date")
    
    # Parse jackpot
    if "Jackpot" in df.columns:
        df["Jackpot"] = (
            df["Jackpot"]
            .astype(str)
            .str.replace("[$,]", "", regex=True)
            .str.extract(r"(\d+)", expand=False)
            .astype(float)
        )
    else:
        df["Jackpot"] = 0
    
    # Identify special ball column
    special_col = None
    if config["special_name"]:
        for col in df.columns:
            if config["special_name"].lower() in col.lower():
                special_col = col
                break
    
    # Split winning numbers into separate columns
    winning_split = (
        df["Winning Numbers"]
        .str.split(",", expand=True)
        .iloc[:, :config["main_count"]]
    )
    
    for col in winning_split.columns:
        winning_split[col] = pd.to_numeric(winning_split[col], errors="coerce")
    
    winning_split = winning_split.dropna().astype(int)
    winning_split.columns = [f"Main_{i}" for i in range(1, config["main_count"] + 1)]
    
    # Align indices
    df = df.loc[winning_split.index].reset_index(drop=True)
    winning_split = winning_split.reset_index(drop=True)
    
    df = pd.concat([df, winning_split], axis=1)
    
    # Validate main numbers
    for i in range(1, config["main_count"] + 1):
        col_name = f"Main_{i}"
        invalid_mask = (df[col_name] < config["main_min"]) | (df[col_name] > config["main_max"])
        if invalid_mask.any():
            # Drop rows with invalid main numbers
            df = df[~invalid_mask]
    
    # Handle special ball
    if special_col:
        df["SpecialBall"] = pd.to_numeric(df[special_col], errors="coerce")
        
        # Validate special ball
        if config["special_min"] is not None and config["special_max"] is not None:
            invalid_mask = (df["SpecialBall"] < config["special_min"]) | (df["SpecialBall"] > config["special_max"])
            if invalid_mask.any():
                # Drop rows with invalid special ball
                df = df[~invalid_mask]
    
    # Add date features
    df["DayOfWeek"] = df["Date"].dt.dayofweek
    df["Month"] = df["Date"].dt.month
    df["Year"] = df["Date"].dt.year
    
    # Create jackpot buckets
    if lottery_type == "fantasy5":
        bins = [0, 100_000, 200_000, 500_000, float('inf')]
    elif lottery_type == "superlotto":
        bins = [0, 10e6, 20e6, 50e6, float('inf')]
    else:
        bins = [0, 100e6, 300e6, 700e6, float('inf')]
    
    df["JackpotBucket"] = pd.cut(
        df["Jackpot"],
        bins=bins,
        labels=["Low", "Mid", "High", "Mega"],
        include_lowest=True
    )
    
    return df


# ============================================================================
# DIFFERENTIAL PRIVACY PROTECTION
# ============================================================================

def add_differential_privacy_noise(predictions, lottery_type, epsilon=0.1):
    """
    Add Laplace noise to predictions to prevent algorithm reverse engineering
    
    This implements differential privacy to protect the Monte Carlo algorithm
    from being reverse-engineered through repeated queries.
    
    Args:
        predictions: List of (main_numbers, special_ball) tuples
        lottery_type: Type of lottery (for getting valid ranges)
        epsilon: Privacy parameter (smaller = more noise, more privacy)
                 Typical values: 0.01 (high privacy) to 1.0 (low privacy)
    
    Returns:
        Noisy predictions with similar statistical properties
    """
    config = LOTTERY_RULES.get(lottery_type)
    if not config:
        raise ValueError(f"Unsupported lottery type: {lottery_type}")
    
    noisy_predictions = []
    
    for main_nums, special in predictions:
        # Add small perturbation to each main number
        main_nums_list = list(main_nums)
        noisy_main = []
        
        for num in main_nums_list:
            # Laplace noise centered at 0
            noise = np.random.laplace(0, 1/epsilon)
            # Round and clamp to valid range
            noisy_val = int(np.clip(num + noise, config["main_min"], config["main_max"]))
            noisy_main.append(noisy_val)
        
        # Remove duplicates (which shouldn't happen in lottery)
        noisy_main = list(set(noisy_main))
        
        # If duplicates occurred, fill with random valid numbers
        while len(noisy_main) < config["main_count"]:
            candidate = np.random.randint(config["main_min"], config["main_max"] + 1)
            if candidate not in noisy_main:
                noisy_main.append(candidate)
        
        # Take only required count and sort
        noisy_main = sorted(noisy_main[:config["main_count"]])
        
        # Add noise to special ball if applicable
        if special is not None and config["special_name"]:
            special_noise = np.random.laplace(0, 1/epsilon)
            noisy_special = int(np.clip(
                special + special_noise, 
                config["special_min"], 
                config["special_max"]
            ))
        else:
            noisy_special = None
        
        noisy_predictions.append((tuple(noisy_main), noisy_special))
    
    # SECURITY: Log that differential privacy was applied
    logger.info(f"Differential privacy applied: lottery_type={lottery_type}, epsilon={epsilon}, predictions_count={len(predictions)}")
    
    return noisy_predictions


# ============================================================================
# MONTE CARLO PREDICTION
# ============================================================================

def predict_next_draw(
    upcoming_jackpot,
    draw_date,
    lottery_type="powerball",
    n_simulations=10000,
    window_years=5,
    random_seed=None,
    csv_path=None,
    log_access=False,
    user_id=None,
    apply_privacy=False,
    epsilon=0.1
):
    """
    Monte Carlo simulation for lottery prediction with security enhancements
    
    Args:
        upcoming_jackpot: Expected jackpot amount
        draw_date: Date of the draw
        lottery_type: Type of lottery (powerball, megamillions, superlotto, fantasy5)
        n_simulations: Number of Monte Carlo simulations
        window_years: Years of historical data to use
        random_seed: Random seed for reproducibility
        csv_path: Path to CSV file with historical data
        log_access: Whether to log data access (SECURITY)
        user_id: User ID for logging (SECURITY)
        apply_privacy: Whether to apply differential privacy (SECURITY)
        epsilon: Privacy parameter for differential privacy (SECURITY)
    
    Returns:
        List of tuples (main_numbers, special_ball)
    """
    if random_seed is not None:
        np.random.seed(random_seed)
    
    config = LOTTERY_RULES[lottery_type]
    
    # SECURITY: Load historical data with access logging
    df = load_lottery_data(lottery_type, csv_path, log_access=log_access, user_id=user_id)
    
    # Filter to recent window
    latest_date = df["Date"].max()
    cutoff_date = latest_date - pd.DateOffset(years=window_years)
    filtered_df = df[df["Date"] >= cutoff_date]

    # If filtering removed everything, fallback to full dataset
    if filtered_df.empty:
        filtered_df = df.copy()

    df = filtered_df
    
    # Determine jackpot bucket
    if lottery_type == "fantasy5":
        bins = [0, 100_000, 200_000, 500_000, float('inf')]
    elif lottery_type == "superlotto":
        bins = [0, 10e6, 20e6, 50e6, float('inf')]
    else:
        bins = [0, 100e6, 300e6, 700e6, float('inf')]
    
    labels = ["Low", "Mid", "High", "Mega"]
    bucket = pd.cut([upcoming_jackpot], bins=bins, labels=labels, include_lowest=True)[0]
    
    # Build frequency distributions
    main_cols = [f"Main_{i}" for i in range(1, config["main_count"] + 1)]
    
    # Melt main numbers into long format
    main_long = pd.melt(
        df,
        id_vars=["JackpotBucket"],
        value_vars=main_cols,
        value_name="Number"
    )
    
    # Calculate frequency distribution
    main_dist = (
        main_long.groupby(["JackpotBucket", "Number"], observed=False)
        .size()
        .reset_index(name="Frequency")
    )
    main_dist = main_dist.set_index(["JackpotBucket", "Number"])["Frequency"]
    
    # Special ball distribution (if applicable)
    special_dist = None
    if config["special_name"]:
        special_dist = (
            df.groupby(["JackpotBucket", "SpecialBall"], observed=False)
            .size()
            .reset_index(name="Frequency")
        )
        special_dist = special_dist.set_index(["JackpotBucket", "SpecialBall"])["Frequency"]
    
    # Prepare probability distributions for the bucket
    def safe_prepare(series, min_required=1):
        if series is None or len(series) < min_required:
            return None
        weights = series.values / series.values.sum()
        numbers = np.array(series.index.get_level_values(-1), dtype=int)
        return numbers, weights
    
    # Main numbers distribution
    main_bucket = main_dist.loc[bucket] if bucket in main_dist.index.get_level_values(0) else None
    main_prepared = safe_prepare(main_bucket, min_required=config["main_count"]) if main_bucket is not None else None
    
    # Fallback to global distribution if bucket doesn't have enough data
    if main_prepared is None:
        global_main = main_dist.groupby(level=1, observed=False).mean().dropna()
        main_numbers_pool = np.array(global_main.index, dtype=int)
        main_weights = global_main.values / global_main.values.sum()
    else:
        main_numbers_pool, main_weights = main_prepared
    
    # Special ball distribution (if applicable)
    special_numbers = None
    special_weights = None
    
    if config["special_name"]:
        special_bucket = special_dist.loc[bucket] if bucket in special_dist.index.get_level_values(0) else None
        special_prepared = safe_prepare(special_bucket, min_required=1) if special_bucket is not None else None
        
        if special_prepared is None:
            global_special = special_dist.groupby(level=1, observed=False).mean().dropna()
            special_numbers = np.array(global_special.index, dtype=int)
            special_weights = global_special.values / global_special.values.sum()
        else:
            special_numbers, special_weights = special_prepared
    
    # SECURITY: Log Monte Carlo execution
    logger.info(f"Monte Carlo execution: lottery_type={lottery_type}, n_simulations={n_simulations}, user_id={user_id}")
    
    # Run Monte Carlo simulations
    results = []
    
    for _ in range(n_simulations):
        # Sample main numbers
        main_numbers = np.random.choice(
            main_numbers_pool,
            size=config["main_count"],
            replace=False,
            p=main_weights
        )
        
        # Sample special ball (if applicable)
        if config["special_name"]:
            special_ball = np.random.choice(special_numbers, p=special_weights)
            results.append((tuple(sorted(main_numbers)), int(special_ball)))
        else:
            # No special ball (Fantasy 5)
            results.append((tuple(sorted(main_numbers)), None))
    
    # SECURITY: Apply differential privacy if requested
    if apply_privacy:
        results = add_differential_privacy_noise(results, lottery_type, epsilon)
    
    return results


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_lottery_config(lottery_type="powerball"):
    """Get configuration for a specific lottery type"""
    if lottery_type not in LOTTERY_RULES:
        raise ValueError(f"Unsupported lottery type: {lottery_type}")
    return LOTTERY_RULES[lottery_type]


def list_supported_lotteries():
    """List all supported lottery types"""
    return list(LOTTERY_RULES.keys())


def sanitize_predictions(predictions, include_metadata=False):
    """
    Sanitize prediction output to prevent information leakage
    
    Args:
        predictions: List of prediction dictionaries
        include_metadata: Whether to include metadata (for premium users)
    
    Returns:
        Sanitized predictions
    """
    sanitized = []
    
    for pred in predictions:
        clean_pred = {
            'numbers': pred['numbers'],
            'special': pred['special']
        }
        
        # Only include metadata if explicitly requested (premium feature)
        if include_metadata and 'confidence' in pred:
            clean_pred['confidence'] = pred['confidence']
        
        sanitized.append(clean_pred)
    
    return sanitized

def run_simulation(lottery_type, num_tickets, jackpot, user_id=None):
    """
    Shared simulation runner used by both selective and blanket security apps.
    Handles predict_next_draw, sampling, and sanitization.

    Args:
        lottery_type: Lottery type string (powerball, megamillions, superlotto, fantasy5)
        num_tickets: Number of tickets to generate
        jackpot: Jackpot amount in dollars
        user_id: User ID for audit logging

    Returns:
        List of sanitized ticket dicts with 'numbers' and 'special' keys
    """

    simulations = predict_next_draw(
        upcoming_jackpot=jackpot,
        draw_date=datetime.now().strftime('%Y-%m-%d'),
        lottery_type=lottery_type,
        n_simulations=num_tickets * 100,
        window_years=5,
        random_seed=None,
        log_access=True,
        user_id=user_id,
        apply_privacy=True,
        epsilon=0.1
    )

    selected = random.sample(simulations, min(num_tickets, len(simulations)))

    tickets = []
    for main_nums, special in selected:
        tickets.append({
            'numbers': list(main_nums),
            'special': special
        })

    return sanitize_predictions(tickets, include_metadata=False)