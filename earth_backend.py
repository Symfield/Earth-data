#!/usr/bin/env python3
"""
Phase-Coherent Earth Dashboard Backend
Fetches REAL data from IERS AND GRACE-FO, applies ⧖-mathematics,
and generates daily JSON updates for the web dashboard.

VERSION: 3.0.0 - IERS + GRACE-FO Real Data!

Data Sources:
1. IERS Earth Orientation Centre (Paris Observatory)
   - x_pole, y_pole (polar motion)
   - UT1-UTC (Earth rotation offset)
   
2. NASA GRACE-FO (via earthaccess)
   - Global mass anomalies
   - Ice sheet changes
   - Groundwater variations

Requirements:
pip install requests numpy earthaccess netCDF4 xarray

Usage:
python earth_backend.py

For GitHub Actions, set these secrets:
- EARTHDATA_USERNAME
- EARTHDATA_PASSWORD
"""

import json
import requests
import numpy as np
import re
from datetime import datetime, timezone
import os

# Try to import earthaccess for GRACE-FO data
try:
    import earthaccess
    EARTHACCESS_AVAILABLE = True
except ImportError:
    EARTHACCESS_AVAILABLE = False
    print("Note: earthaccess not installed. GRACE-FO data will be simulated.")
    print("Install with: pip install earthaccess")

# Try to import xarray for reading netCDF files
try:
    import xarray as xr
    XARRAY_AVAILABLE = True
except ImportError:
    XARRAY_AVAILABLE = False


class PhaseCoherentEarthBackend:
    def __init__(self):
        # IERS data source (publicly accessible, no auth needed!)
        self.iers_url = "https://hpiers.obspm.fr/eop-pc/index.php"
        
        # GRACE-FO dataset short name
        self.grace_dataset = "TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4"
        
        # Phase-coherent parameters (from your framework)
        self.alpha = 0.03
        self.lambda_eff = 0.1
        self.kappa = 0.05
        
        # Current state - will be updated with real data
        self.semi_axes = {'a': 1.0501, 'b': 0.9823, 'c': 0.9477}
        self.fuzzy_weights = [0.95, 0.87, 0.72, 0.58, 0.41]
        self.bias_vector = {'x': 0.15, 'y': 0.02, 'z': 0.08}
        self.fci = 1.96
        self.itci = 2.31
        
        # Store data for output
        self.iers_data = None
        self.grace_data = None
        
        # Load previous state if available (for continuity)
        self.load_previous_state()
    
    def load_previous_state(self):
        """Load previous state for ⧖-preserving continuity."""
        try:
            if os.path.exists('earth_data.json'):
                with open('earth_data.json', 'r') as f:
                    prev = json.load(f)
                
                # Handle both old format (semi_axes) and new format (metric_tensor)
                if 'metric_tensor' in prev:
                    self.semi_axes = prev['metric_tensor']
                elif 'semi_axes' in prev:
                    self.semi_axes = prev['semi_axes']
                    
                if 'fuzzy_weights' in prev:
                    self.fuzzy_weights = prev['fuzzy_weights']
                    
                if 'bias_vector' in prev:
                    bv = prev['bias_vector']
                    if isinstance(bv, list):
                        self.bias_vector = {'x': bv[0], 'y': bv[1], 'z': bv[2]}
                    else:
                        self.bias_vector = bv
                        
                if 'fci' in prev:
                    self.fci = prev['fci']
                elif 'field_coherence_index' in prev:
                    self.fci = prev['field_coherence_index']
                    
                if 'itci' in prev:
                    self.itci = prev['itci']
                    
                print("✓ Loaded previous state for continuity")
        except Exception as e:
            print(f"Starting fresh (no previous state): {e}")

    def fetch_iers_data(self):
        """
        Fetch REAL IERS polar motion data from Paris Observatory.
        This is ACTUAL Earth orientation data, not simulated!
        """
        print(f"\n📡 Fetching REAL IERS data from: {self.iers_url}")
        
        try:
            response = requests.get(self.iers_url, timeout=30)
            response.raise_for_status()
            text = response.text
            
            # Parse the latest C04 values from the page
            x_match = re.search(r'x=\s*([\d.]+)\s*mas', text)
            y_match = re.search(r'y=\s*([\d.]+)\s*mas', text)
            ut1_match = re.search(r'UT1-UTC=\s*([\d.-]+)\s*ms', text)
            date_match = re.search(r'on\s+\*\*(\d+)\s+(\w+)\s+(\d+)\*\*', text)
            
            if x_match and y_match and ut1_match:
                self.iers_data = {
                    'x_pole_mas': float(x_match.group(1)),
                    'y_pole_mas': float(y_match.group(1)),
                    'ut1_utc_ms': float(ut1_match.group(1)),
                    'source': 'IERS_C04_REAL',
                    'quality': 'good'
                }
                
                if date_match:
                    self.iers_data['data_date'] = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}"
                
                print(f"✓ REAL IERS data fetched:")
                print(f"  x_pole: {self.iers_data['x_pole_mas']} mas")
                print(f"  y_pole: {self.iers_data['y_pole_mas']} mas")
                print(f"  UT1-UTC: {self.iers_data['ut1_utc_ms']} ms")
                
                return self.iers_data
            else:
                raise ValueError("Could not parse IERS page")
                
        except Exception as e:
            print(f"✗ IERS fetch failed: {e}")
            self.iers_data = {
                'x_pole_mas': 120.0,
                'y_pole_mas': 316.0,
                'ut1_utc_ms': 75.0,
                'source': 'FALLBACK',
                'quality': 'estimated'
            }
            return self.iers_data

    def fetch_grace_data(self):
        """
        Fetch REAL GRACE-FO mascon data from NASA.
        Requires earthaccess library and Earthdata credentials.
        """
        print(f"\n🛰️ Fetching GRACE-FO data...")
        
        if not EARTHACCESS_AVAILABLE:
            print("  earthaccess not available, using estimated values")
            return self._grace_fallback()
        
        try:
            # Authenticate with Earthdata
            # Credentials come from environment variables or .netrc
            auth = earthaccess.login()
            
            if not auth.authenticated:
                print("  Not authenticated, trying environment variables...")
                # GitHub Actions sets these from secrets
                username = os.environ.get('EARTHDATA_USERNAME')
                password = os.environ.get('EARTHDATA_PASSWORD')
                
                if username and password:
                    auth = earthaccess.login(strategy="environment")
                else:
                    print("  No credentials found, using fallback data")
                    return self._grace_fallback()
            
            print(f"✓ Authenticated with NASA Earthdata")
            
            # Search for latest GRACE-FO mascon data
            results = earthaccess.search_data(
                short_name=self.grace_dataset,
                count=1  # Just get the most recent file
            )
            
            if not results:
                print("  No GRACE-FO data found, using fallback")
                return self._grace_fallback()
            
            print(f"  Found {len(results)} GRACE-FO granule(s)")
            
            # Download the most recent file
            if XARRAY_AVAILABLE:
                # Stream directly into xarray
                files = earthaccess.open(results)
                ds = xr.open_dataset(files[0])
                
                # Extract global mean mass anomaly
                # The mascon data contains 'lwe_thickness' (liquid water equivalent)
                if 'lwe_thickness' in ds:
                    lwe = ds['lwe_thickness']
                    
                    # Compute global statistics
                    global_mean = float(lwe.mean().values)
                    global_std = float(lwe.std().values)
                    
                    # Get regional values (approximate)
                    # Greenland region (60-85°N, -75 to -10°E)
                    greenland = lwe.sel(lat=slice(60, 85), lon=slice(-75, -10)).mean().values
                    
                    # Antarctica region (-90 to -60°S)
                    antarctica = lwe.sel(lat=slice(-90, -60)).mean().values
                    
                    self.grace_data = {
                        'global_mean_lwe_cm': round(float(global_mean), 3),
                        'global_std_lwe_cm': round(float(global_std), 3),
                        'greenland_lwe_cm': round(float(greenland), 3) if not np.isnan(greenland) else 0,
                        'antarctica_lwe_cm': round(float(antarctica), 3) if not np.isnan(antarctica) else 0,
                        'source': 'GRACE-FO_REAL',
                        'dataset': self.grace_dataset,
                        'quality': 'good'
                    }
                    
                    ds.close()
                    
                    print(f"✓ REAL GRACE-FO data processed:")
                    print(f"  Global mean LWE: {self.grace_data['global_mean_lwe_cm']} cm")
                    print(f"  Global std LWE: {self.grace_data['global_std_lwe_cm']} cm")
                    
                    return self.grace_data
                else:
                    print("  lwe_thickness not found in dataset")
                    ds.close()
                    return self._grace_fallback()
            else:
                # Download to temp file if xarray not available
                downloaded = earthaccess.download(results, "./temp_grace")
                print(f"  Downloaded to: {downloaded}")
                # Would need netCDF4 to process
                return self._grace_fallback()
                
        except Exception as e:
            print(f"✗ GRACE-FO fetch failed: {e}")
            return self._grace_fallback()
    
    def _grace_fallback(self):
        """Provide estimated GRACE-FO values when real data unavailable."""
        self.grace_data = {
            'global_mean_lwe_cm': round(np.random.normal(0, 5), 3),
            'global_std_lwe_cm': round(abs(np.random.normal(15, 3)), 3),
            'greenland_lwe_cm': round(np.random.normal(-200, 30), 3),  # Greenland losing mass
            'antarctica_lwe_cm': round(np.random.normal(-100, 20), 3),  # Antarctica losing mass
            'source': 'ESTIMATED',
            'quality': 'estimated'
        }
        print(f"  Using estimated GRACE values")
        return self.grace_data

    def apply_tau_update(self):
        """
        Apply ⧖-preserving update to metric tensor using REAL data.
        Combines IERS (rotation) and GRACE-FO (mass) information.
        """
        print(f"\n⧖ Applying phase-coherent update...")
        
        if not self.iers_data:
            print("  No IERS data available")
            return
        
        # === IERS contribution (rotational dynamics) ===
        x_pole = self.iers_data['x_pole_mas']
        y_pole = self.iers_data['y_pole_mas']
        ut1_utc = self.iers_data['ut1_utc_ms']
        
        pole_magnitude = np.sqrt(x_pole**2 + y_pole**2)
        pole_angle = np.arctan2(y_pole, x_pole)
        
        # Rotational strain from polar motion
        strain_scale = 1e-6
        delta_a_rot = x_pole * strain_scale * np.cos(pole_angle)
        delta_b_rot = y_pole * strain_scale * np.sin(pole_angle)
        delta_c_rot = -ut1_utc * strain_scale * 0.1
        
        # === GRACE-FO contribution (mass dynamics) ===
        delta_a_mass = 0
        delta_b_mass = 0
        delta_c_mass = 0
        
        if self.grace_data and self.grace_data.get('quality') != 'estimated':
            # Mass redistribution affects Earth's shape
            global_lwe = self.grace_data.get('global_mean_lwe_cm', 0)
            greenland = self.grace_data.get('greenland_lwe_cm', 0)
            antarctica = self.grace_data.get('antarctica_lwe_cm', 0)
            
            # Ice loss at poles increases oblateness (c gets smaller relative to a,b)
            mass_scale = 1e-8
            delta_a_mass = -greenland * mass_scale * 0.3  # Northern hemisphere effect
            delta_b_mass = -greenland * mass_scale * 0.3
            delta_c_mass = (greenland + antarctica) * mass_scale * 0.1  # Polar mass loss
            
            print(f"  GRACE-FO contribution: Δa={delta_a_mass:.9f}, Δb={delta_b_mass:.9f}, Δc={delta_c_mass:.9f}")
        
        # === Combined update ===
        delta_a = delta_a_rot + delta_a_mass
        delta_b = delta_b_rot + delta_b_mass
        delta_c = delta_c_rot + delta_c_mass
        
        # ⧖-preserving update: blend new with existing
        old_a = self.semi_axes['a']
        old_b = self.semi_axes['b']
        old_c = self.semi_axes['c']
        
        self.semi_axes['a'] = old_a * (1 - self.alpha) + (1.0 + delta_a) * self.alpha + old_a * self.alpha
        self.semi_axes['b'] = old_b * (1 - self.alpha) + (1.0 + delta_b) * self.alpha + old_b * self.alpha * 0.98
        self.semi_axes['c'] = old_c * (1 - self.alpha) + (0.9966 + delta_c) * self.alpha + old_c * self.alpha * 0.95
        
        # Keep semi-axes in reasonable range
        self.semi_axes['a'] = max(0.95, min(1.10, self.semi_axes['a']))
        self.semi_axes['b'] = max(0.95, min(1.05, self.semi_axes['b']))
        self.semi_axes['c'] = max(0.90, min(1.00, self.semi_axes['c']))
        
        print(f"  Metric tensor updated:")
        print(f"    a: {old_a:.6f} → {self.semi_axes['a']:.6f}")
        print(f"    b: {old_b:.6f} → {self.semi_axes['b']:.6f}")
        print(f"    c: {old_c:.6f} → {self.semi_axes['c']:.6f}")
        
        # Update fuzzy weights with gentle decay
        for i in range(len(self.fuzzy_weights)):
            old_weight = self.fuzzy_weights[i]
            decay = np.exp(-0.01 * (i + 1))
            self.fuzzy_weights[i] = max(0.30, min(0.98, old_weight * decay))
        
        print(f"  μ weights: {[f'{w:.3f}' for w in self.fuzzy_weights]}")
    
    def compute_bias_vector(self):
        """
        Compute bias vector from polar motion and mass distribution.
        """
        if not self.iers_data:
            return
            
        x_pole = self.iers_data['x_pole_mas']
        y_pole = self.iers_data['y_pole_mas']
        
        magnitude = np.sqrt(x_pole**2 + y_pole**2)
        if magnitude > 0:
            norm_x = x_pole / magnitude
            norm_y = y_pole / magnitude
        else:
            norm_x, norm_y = 0, 0
        
        # Add GRACE contribution to z-component (mass imbalance)
        z_contribution = 0
        if self.grace_data:
            greenland = self.grace_data.get('greenland_lwe_cm', 0)
            antarctica = self.grace_data.get('antarctica_lwe_cm', 0)
            # North-south mass imbalance affects z bias
            z_contribution = (greenland - antarctica) * 1e-5
        
        # ⧖-preserving blend
        self.bias_vector['x'] = self.bias_vector['x'] * 0.9 + norm_x * 0.1
        self.bias_vector['y'] = self.bias_vector['y'] * 0.9 + norm_y * 0.1
        self.bias_vector['z'] = self.bias_vector['z'] * 0.9 + z_contribution * 0.1
        
        for key in self.bias_vector:
            self.bias_vector[key] = max(-0.5, min(0.5, self.bias_vector[key]))
        
        print(f"  Bias vector: [{self.bias_vector['x']:.4f}, {self.bias_vector['y']:.4f}, {self.bias_vector['z']:.4f}]")
    
    def compute_coherence_indices(self):
        """
        Compute Field Coherence Index (FCI) and Information-Theoretic Coherence Index (ITCI).
        """
        weights_variance = np.var(self.fuzzy_weights)
        self.fci = 2.0 / (1 + weights_variance * 10)
        
        # Boost based on data quality
        quality_boost = 1.0
        if self.iers_data and self.iers_data.get('quality') == 'good':
            quality_boost += 0.02
        if self.grace_data and self.grace_data.get('quality') == 'good':
            quality_boost += 0.03
        
        self.fci *= quality_boost
        self.fci = max(1.5, min(2.5, self.fci))
        
        # ITCI: Shannon entropy
        weights = np.array(self.fuzzy_weights)
        weights = weights / np.sum(weights)
        self.itci = -np.sum(weights * np.log(weights + 1e-10))
        self.itci = max(1.8, min(2.8, self.itci))
        
        print(f"  Coherence: FCI={self.fci:.3f}, ITCI={self.itci:.3f}")
    
    def generate_dashboard_update(self):
        """
        Generate JSON update for the dashboard.
        """
        now = datetime.now(timezone.utc)
        
        # Determine overall data source
        sources = []
        if self.iers_data:
            sources.append(self.iers_data.get('source', 'unknown'))
        if self.grace_data:
            sources.append(self.grace_data.get('source', 'unknown'))
        
        update_data = {
            'timestamp': now.isoformat(),
            'last_updated': now.isoformat(),
            'status': 'live',

            # Legacy keys (kept verbatim — the dashboard reads these)
            'semi_axes': self.semi_axes,
            'bias_vector': self.bias_vector,
            'fuzzy_weights': self.fuzzy_weights,
            'fci': round(self.fci, 4),
            'itci': round(self.itci, 4),
            'field_coherence_index': round(self.fci, 4),
            'metric_tensor': {
                'a': round(self.semi_axes['a'], 6),
                'b': round(self.semi_axes['b'], 6),
                'c': round(self.semi_axes['c'], 6)
            },

            # Real data included for transparency
            'iers_data': self.iers_data if self.iers_data else {},
            'grace_data': self.grace_data if self.grace_data else {},

            # V2 vocabulary (paper-aligned; values mirror the legacy fields)
            'v2': {
                'ring_weights_r': self.fuzzy_weights,          # retrievability r0..r4
                'fci_legacy_estimator': round(self.fci, 4),    # V1 variance proxy, kept for continuity
                'ring_profile_MH': {                           # (M, H) over the ring profile
                    'M': round(float(np.mean(self.fuzzy_weights)), 4),
                    'H': round(float(-sum(
                        (w / sum(self.fuzzy_weights)) * np.log(w / sum(self.fuzzy_weights))
                        for w in self.fuzzy_weights)) / float(np.log(len(self.fuzzy_weights))), 4)
                },
                'estimators': {
                    'bias_vector': 'EMA of unit pole direction (declared simplified estimator)',
                    'coherence': 'component readout (C_lin, C_phase, C_circ, C_amp) pending first measured benchmark'
                },
                'notes': 'Coherence = persistence of relational structure through change; '
                         'rings are retrievability, not coherence. See paper V2.'
            },

            # V2: AI-mirror status removed — cross-model checks are consistency
            # procedures requiring logged execution artifacts, not a live badge.

            'data_sources': sources,
            'data_quality': 'good' if 'REAL' in str(sources) else 'estimated',
            'framework_version': '3.2.0-v2-vocabulary'
        }

        return update_data
    
    def save_daily_update(self, data):
        """Save daily update to JSON files."""
        # Dated backup
        filename = f"earth_data_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 Saved: {filename}")
        
        # Main file
        with open('earth_data.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved: earth_data.json")
        
        # Compatibility file
        with open('latest.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def run_daily_update(self):
        """Execute complete daily update cycle with REAL data."""
        print("\n" + "="*60)
        print("🌍 PHASE-COHERENT EARTH MONITOR")
        print("   Real Data Update: IERS + GRACE-FO")
        print(f"⏰ {datetime.now(timezone.utc).isoformat()}")
        print("="*60)
        
        # 1. Fetch real data
        self.fetch_iers_data()
        self.fetch_grace_data()
        
        # 2. Apply phase-coherent mathematics
        self.apply_tau_update()
        self.compute_bias_vector()
        self.compute_coherence_indices()
        
        # 3. Generate and save
        update_data = self.generate_dashboard_update()
        self.save_daily_update(update_data)
        
        print("\n" + "="*60)
        print("✅ UPDATE COMPLETE")
        print("="*60)
        
        return update_data


def main():
    """Main execution function for GitHub Actions."""
    backend = PhaseCoherentEarthBackend()
    update_data = backend.run_daily_update()
    
    # Summary
    print(f"\n📊 Earth Field State Summary:")
    print(f"   Data Sources: {update_data.get('data_sources', [])}")
    print(f"   Semi-axes: a={update_data['semi_axes']['a']:.4f}, "
          f"b={update_data['semi_axes']['b']:.4f}, "
          f"c={update_data['semi_axes']['c']:.4f}")
    print(f"   Coherence: FCI={update_data['fci']:.3f}, ITCI={update_data['itci']:.3f}")


if __name__ == "__main__":
    main()
