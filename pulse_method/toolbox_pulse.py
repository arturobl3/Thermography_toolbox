import numpy as np
import os
import glob
import re
from numpy.fft import fft
from scipy.linalg import svd,eig,inv
from scipy.stats import skew, kurtosis
from sklearn.preprocessing import MinMaxScaler
from scipy.signal import savgol_filter
import pywt
from scipy.stats import median_abs_deviation as mad
import torch
import torch.fft
import torch.nn.functional as F

class thermograms:
    """
    Class which handles classic method of thermography from sequence of data in shape (N,H,W)

    Methods inside of this class allow to read data from .bin format when directory path is provided.

    Used algorithms:
        - Pulse Phase Thermography (PPT)
        - Principal Component Thermograpghy (PCT)
        - Thermography Signal Reconstruction (TSR)
        - Highier Order Statistic Thermography (HOS)
        - Dynamic Mode Decomposition (DMD)

    Filtering methods:
        - Savitzki-Golay filtering (SavGol)
        - Denoising using wavelet filter (WaveFil)
        - Binarization of thermography frame (binarize_mask)
        - Mean average filter (MeanFil)

    Data loading methods:
        - Formulating thermography sequence from .bin files (loadfrombinfiles)
        - Formulating thermography sequence from .csv files (loadfromcsvfiles)
    
    """
    def __init__(self,height=512,width=640):
        self.height=height
        self.width=width

    #--------------------------------------------------------------------------------Formulating sequence-----------------------------------------------------------------------------

    def load_bin(self, file_path, dtype):
        """
        Load a binary (.bin) file recorded by an infrared camera and reshape it into a 2D image array.

        Args:
            file_path (str): Path to the binary file to be loaded.
            dtype (str or numpy.dtype): Data type used to interpret the binary file 
                                    (e.g., 'float32', 'uint16').

        Returns:
            numpy.ndarray: A 2D array of shape (height, width) containing the thermal image data.

        Notes:
            - The binary file is expected to contain raw pixel values in sequential order.
            - The reshaping uses the class attributes 'height' and 'width' which should be 
            set according to the camera's resolution.
            - No header or metadata is expected in the binary file - pure pixel values only.
        """
        # Read raw binary data into 1D numpy array
        data = np.fromfile(file_path, dtype=dtype)
        
        # Reshape the 1D array into 2D image format using class-defined dimensions
        return data.reshape((self.height, self.width))

    def get_sorted_filenames(self, directory):
        """
        Extracts and sorts filenames of thermogram files in a directory based on numerical ordering.
        
        The method expects filenames containing numbers (e.g., 'frame_0.bin', 'frame_1.bin') and
        sorts them numerically rather than lexicographically to ensure proper sequence ordering.

        Args:
            directory (str): Path to the directory containing thermogram files.

        Returns:
            list: A sorted list of filenames in numerical order based on the embedded numbers.
                Only regular files are included (subdirectories are ignored).

        Raises:
            FileNotFoundError: If the specified directory does not exist.
            
        Notes:
            - Files without numbers in their names will be sorted to the beginning (assigned -1).
            - The sorting is case-sensitive.
            - Hidden files (starting with '.') are included if they match the pattern.
        """
        def extract_number(filename):
            """
            Helper function to extract numerical value from filename.
            
            Args:
                filename (str): The filename to process.
                
            Returns:
                int: The extracted number, or -1 if no number is found.
            """
            match = re.search(r'\d+', filename)  # Find first sequence of digits
            return int(match.group()) if match else -1  # Default to -1 if no number found

        # Verify directory exists
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")

        # Get and sort files by embedded numbers
        return sorted(
            [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))],
            key=extract_number
        )

    def loadfrombinfiles(self, dir_path, dtype=np.uint16):
        """
        Loads a sequence of binary thermogram files into a 3D numpy array stack.

        Args:
            dir_path (str): Path to directory containing binary thermogram files.
            dtype (numpy.dtype, optional): Data type of the binary files. Defaults to np.uint16.

        Returns:
            numpy.ndarray: A 3D array of shape (N, H, W) where:
                - N: Number of frames
                - H: Height of each frame (pixels)
                - W: Width of each frame (pixels)

        Raises:
            FileNotFoundError: If the directory doesn't exist or contains no files.
            ValueError: If loaded frames have inconsistent dimensions.

        Notes:
            - Files are loaded in numerical order using get_sorted_filenames()
            - All files must have the same dimensions (H, W)
            - Memory usage can be high for large sequences (consider memory mapping)
        """
        # Get sorted list of files in directory
        list_of_files = self.get_sorted_filenames(directory=dir_path)
        if not list_of_files:
            raise FileNotFoundError(f"No files found in directory: {dir_path}")

        # Pre-allocate array for better performance with large sequences
        sample_frame = self.load_bin(os.path.join(dir_path, list_of_files[0]), dtype)
        num_frames = len(list_of_files)
        height, width = sample_frame.shape
        frames = np.empty((num_frames, height, width), dtype=dtype)

        # Load all frames into pre-allocated array
        for i in range(num_frames):
            full_path = os.path.join(dir_path, list_of_files[i])
            frames[i] = self.load_bin(full_path, dtype=dtype)

            # Verify consistent dimensions
            if frames[i].shape != (height, width):
                raise ValueError(f"Frame {list_of_files[i]} has inconsistent dimensions. "
                            f"Expected {(height, width)}, got {frames[i].shape}")

        return frames

    

    def loadfromcsvfiles(self, dir_path):
        """
        Loads a sequence of CSV thermogram files into a 3D numpy array stack.

        Args:
            dir_path (str): Path to directory containing CSV thermogram files. Files should be
                        named with numerical identifiers (e.g., 'frame_0.csv', 'frame_1.csv').

        Returns:
            numpy.ndarray: A 3D array of shape (N, H, W) where:
                - N: Number of frames
                - H: Height of each frame (rows)
                - W: Width of each frame (columns)

        Raises:
            FileNotFoundError: If the directory doesn't exist or contains no CSV files.
            ValueError: If loaded frames have inconsistent dimensions or invalid data.
            RuntimeError: If CSV files cannot be parsed (invalid format or delimiter).

        Notes:
            - Files are sorted numerically by embedded numbers in filenames
            - All CSV files must:
            * Use comma delimiter
            * Have consistent dimensions
            * Contain only numeric values
            - Files without numbers in names are sorted last
        """
        def extract_number(file_name):
            """
            Helper function to extract numerical value from filename.
            
            Args:
                file_name (str): The filename to process
                
            Returns:
                int/float: The extracted number, or infinity if no number found
            """
            match = re.search(r'\d+', os.path.basename(file_name))
            return int(match.group()) if match else float('inf')

        # Get and sort CSV files
        csv_files = glob.glob(os.path.join(dir_path, "*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in directory: {dir_path}")
        csv_files.sort(key=extract_number)

        # Load first file to get dimensions
        try:
            sample_frame = np.loadtxt(csv_files[0], delimiter=",")
        except Exception as e:
            raise RuntimeError(f"Failed to load {csv_files[0]}: {str(e)}") from e

        # Pre-allocate array
        num_frames = len(csv_files)
        height, width = sample_frame.shape
        frames = np.empty((num_frames, height, width), dtype=np.float32)

        # Load all frames with validation
        for i, csv_file in enumerate(csv_files):
            try:
                data = np.loadtxt(csv_file, delimiter=",")
                if data.shape != (height, width):
                    raise ValueError(
                        f"File {os.path.basename(csv_file)} has dimensions {data.shape}, "
                        f"expected {(height, width)}"
                    )
                frames[i] = data
            except Exception as e:
                raise RuntimeError(f"Error processing {csv_file}: {str(e)}") from e

        return frames

    
    #--------------------------------------------------------------------------------Detection methods-----------------------------------------------------------------------------

    def PPT(self,data, mode_num=15):
        """
        Pulse Phase Thermography (PPT) via FFT-based phase analysis.
        
        Args:
            data: 3D array (N_frames, H, W) - Thermal sequence.
            mode_num: Number of FFT modes to return (default=15).
            
        Returns:
            phasegram: Shape (mode_num, H, W) - Phase spectra of first `mode_num` frequencies.
            magnitude: (Optional) Magnitude spectra for signal energy analysis.
        """
        # FFT along time axis (N_frames)
        fft_result = fft(data, axis=0)
        
        # Phase and magnitude spectra
        phasegram = np.angle(fft_result[:mode_num])  # (mode_num, H, W)
        magnitude = np.abs(fft_result[:mode_num])    # Optional: for energy analysis
        
        return phasegram, magnitude  # Or just return phasegram if magnitude isn't needed
    

    def PPT_torch(self, data, mode_num=15):
        """
        Pulse Phase Thermography (PPT) via FFT-based phase analysis (PyTorch version).
        
        Args:
            data: 3D tensor (N_frames, H, W) - Thermal sequence.
            mode_num: Number of FFT modes to return (default=15).
            
        Returns:
            phasegram: Shape (mode_num, H, W) - Phase spectra of first `mode_num` frequencies.
            magnitude: (Optional) Magnitude spectra for signal energy analysis.
        """
        # Ensure input is a tensor
        if not isinstance(data, torch.Tensor):
            data = torch.tensor(data, dtype=torch.float32)
        
        # FFT along time axis (axis=0)
        fft_result = torch.fft.fft(data, dim=0)  # (N_frames, H, W)
        
        # Extract phase and magnitude
        phasegram = torch.angle(fft_result[:mode_num])  # (mode_num, H, W)
        magnitude = torch.abs(fft_result[:mode_num])    # Optional: magnitude spectra
        
        return phasegram, magnitude

    
    def PCT(self, data, n_components=10):
        """
        Principal Component Thermography (PCT) via SVD (NumPy version).
        
        Args:
            data: 3D array (N_frames, H, W) - Thermal sequence.
            n_components: Number of principal components to return. If None, returns all.
            
        Returns:
            EOFs: Empirical Orthogonal Functions (n_components, H, W).
            s: Singular values (n_components,).
        """
        N, H, W = data.shape

        # Flatten to (N, H*W): samples x features
        data_flat = data.reshape(N, -1)

        # Mean-center features (column-wise)
        mean = np.mean(data_flat, axis=0, keepdims=True)
        data_centered = data_flat - mean

        # SVD
        U, s, Vh = svd(data_centered, full_matrices=False)  # Vh: (N, H*W)

        # Principal directions = Vh (rows are principal components)
        EOFs = Vh[:n_components].reshape(-1, H, W) if n_components else Vh.reshape(-1, H, W)

        # Truncate singular values
        s = s[:n_components] if n_components else s

        return EOFs, s
    
    def PCT_torch(self, data, n_components=10, fast_svd=False):
        """
        Principal Component Thermography (PCT) via SVD (PyTorch version).
        
        Args:
            data: 3D tensor (N_frames, H, W) - Thermal sequence.
            n_components: Number of principal components to return.
            fast_svd: Use randomized SVD.
        
        Returns:
            EOFs: Spatial modes (n_components, H, W).
            s: Singular values (n_components,).
        """
        if not isinstance(data, torch.Tensor):
            data = torch.tensor(data, dtype=torch.float32)

        T, H, W = data.shape

        # Flatten to (T, H*W): samples x features
        data_flat = data.reshape(T, -1)  # shape (T, H*W)

        # Subtract mean from each column (feature-wise centering)
        mean = data_flat.mean(dim=0, keepdim=True)
        data_centered = data_flat - mean

        # Perform SVD
        with torch.no_grad():
            if fast_svd:
                q = min(n_components or 10, min(data_centered.shape))
                U, s, V = torch.svd_lowrank(data_centered, q=q)
            else:
                U, s, Vh = torch.linalg.svd(data_centered, full_matrices=False)

        # Vh has shape (T, H*W) → spatial EOFs are rows of Vh
        EOFs = Vh[:n_components].reshape(n_components, H, W)

        return EOFs, s[:n_components]
        
    def TSR(self, data, polynomial_order=7):
        """
        Thermographic Signal Reconstruction (TSR) via logarithmic polynomial fitting (NumPy version).
        
        Args:
            data: 3D array (N_frames, H, W) - Thermal sequence.
            polynomial_order: Order of the polynomial (e.g., 7).
            
        Returns:
            coefficient_matrix: Shape (polynomial_order + 1, H, W).
                Each [k, i, j] contains the k-th coefficient for pixel (i, j).
                Order: [highest_order, ..., constant_term].
            reconstructed: Shape (N_frames, H, W) - Reconstructed thermal decays.
        """
        N, H, W = data.shape

        # Time vector and normalized logarithm
        x = np.arange(1, N + 1)
        x_log = np.log(x)
        x_log = (x_log - np.mean(x_log)) / np.std(x_log)

        # Safe log-transform of data
        data_log = np.log(data + 1e-10)  # Shape: (N, H, W)
        data_log_flat = data_log.reshape(N, -1)  # Shape: (N, H*W)

        # Polynomial fit for all pixels (axis=0: time)
        coefficients_flat = np.polyfit(x_log, data_log_flat, polynomial_order)  # Shape: (order+1, H*W)

        # Reshape coefficients to (order+1, H, W)
        coefficient_matrix = coefficients_flat.reshape(polynomial_order + 1, H, W)

        # Reconstruct log-domain signal
        X_rebuild = np.stack([x_log**(polynomial_order - i) for i in range(polynomial_order + 1)], axis=1)  # (N, order+1)
        reconstructed_log = X_rebuild @ coefficients_flat  # (N, H*W)

        # Convert back from log-domain to normal
        reconstructed = np.exp(reconstructed_log).reshape(N, H, W)  # (N, H, W)

        # Compute R² map
        y_true = data_log_flat  # (N, H*W)
        y_pred = reconstructed_log
        ss_res = np.sum((y_true - y_pred)**2, axis=0)
        ss_tot = np.sum((y_true - np.mean(y_true, axis=0))**2, axis=0)
        r2_flat = 1 - (ss_res / (ss_tot + 1e-12))
        r2_map = r2_flat.reshape(H, W)



        return coefficient_matrix, reconstructed,r2_map
    

    def TSR_torch(self, data, polynomial_order=7):
        """
        Thermographic Signal Reconstruction (TSR) via logarithmic polynomial fitting (PyTorch version).
        
        Args:
            data: 3D tensor (N_frames, H, W) - Thermal sequence.
            polynomial_order: Order of the polynomial (default=7).
            
        Returns:
            coefficient_matrix: Shape (polynomial_order + 1, H, W).
                Each [k, i, j] contains the k-th coefficient for pixel (i, j).
                Order: [highest_order, ..., constant_term].
            reconstructed: Denoised thermal sequence (N_frames, H, W).
        """
        # Ensure input is a tensor
        if not isinstance(data, torch.Tensor):
            data = torch.tensor(data, dtype=torch.float32)
        
        N, H, W = data.shape
        
        # Time vector and normalized log
        x = torch.arange(1, N + 1, device=data.device, dtype=data.dtype)  # (N,)
        x_log = torch.log(x)
        x_log = (x_log - x_log.mean()) / x_log.std()

        # Log-transform thermal data
        data_log = torch.log(data + 1e-10)  # (N, H, W)
        data_log_flat = data_log.view(N, -1)  # (N, H*W)

        # Vandermonde matrix (N, order+1)
        X = torch.stack([x_log ** (polynomial_order - i) for i in range(polynomial_order + 1)], dim=1)

        # Solve least-squares: X @ coeffs = data_log_flat
        coefficients_flat, *_ = torch.linalg.lstsq(X, data_log_flat)

        # Reshape coefficients to (order+1, H, W)
        coefficient_matrix = coefficients_flat.view(polynomial_order + 1, H, W)

        # Reconstruct fitted signal (still in log-space)
        reconstructed_log = X @ coefficients_flat  # (N, H*W)
        reconstructed = torch.exp(reconstructed_log).view(N, H, W)  # (N, H, W)


        # Compute R²
        y_true = data_log_flat
        y_pred = reconstructed_log
        ss_res = torch.sum((y_true - y_pred)**2, dim=0)
        ss_tot = torch.sum((y_true - y_true.mean(dim=0))**2, dim=0)
        r2_flat = 1 - (ss_res / (ss_tot + 1e-12))
        r2_map = r2_flat.view(H, W)

        return coefficient_matrix, reconstructed, r2_map


    def HOS(self,data):
        """
        Compute Higher-Order Statistics (Skewness, Kurtosis, 5th Moment) for each pixel.
        
        Args:
            data: 3D array (N_frames, H, W) - Thermal sequence.
            
        Returns:
            HOS_matrix: Shape (3, H, W) where:
                [0,:,:] = Skewness
                [1,:,:] = Kurtosis
                [2,:,:] = 5th standardized central moment
        """
        # Reshape to (N_frames, H*W) for vectorized operations
        data_flat = data.reshape(data.shape[0], -1)  # (N, H*W)
        
        # Compute skewness and kurtosis (vectorized)
        skew_image = skew(data_flat, axis=0).reshape(data.shape[1], data.shape[2])
        kurtosis_image = kurtosis(data_flat, axis=0).reshape(data.shape[1], data.shape[2])
        
        # Compute 5th standardized central moment (vectorized)
        standardized = (data_flat - np.mean(data_flat, axis=0)) / np.std(data_flat, axis=0, where=(np.std(data_flat, axis=0) != 0))
        fifth_moment = np.mean(standardized**5, axis=0).reshape(data.shape[1], data.shape[2])
        
        # Stack results
        HOS_matrix = np.stack([skew_image, kurtosis_image, fifth_moment], axis=0)
        
        return HOS_matrix
    
    def HOS_torch(self, data):
        """
        Compute Higher-Order Statistics (Skewness, Kurtosis, 5th Moment) for each pixel (PyTorch version).
        
        Args:
            data: 3D tensor (N_frames, H, W) - Thermal sequence.
                
        Returns:
            HOS_matrix: Shape (3, H, W) where:
                [0,:,:] = Skewness
                [1,:,:] = Kurtosis
                [2,:,:] = 5th standardized central moment
        """
        # Ensure input is a tensor
        if not isinstance(data, torch.Tensor):
            data = torch.tensor(data, dtype=torch.float32)
        
        N, H, W = data.shape
        data_flat = data.reshape(N, -1)  # (N, H*W)
        
        # Compute mean and std (with zero-std protection)
        mean = torch.mean(data_flat, dim=0)
        std = torch.std(data_flat, dim=0)
        std[std == 0] = 1.0  # Avoid division by zero
        
        # Standardized data
        standardized = (data_flat - mean) / std
        
        # Skewness (3rd standardized moment)
        skewness = torch.mean(standardized ** 3, dim=0)
        
        # Kurtosis (4th standardized moment, excess=False)
        kurtosis = torch.mean(standardized ** 4, dim=0)
        
        # 5th standardized central moment
        fifth_moment = torch.mean(standardized ** 5, dim=0)
        
        # Reshape and stack results
        HOS_matrix = torch.stack([
            skewness.reshape(H, W),
            kurtosis.reshape(H, W),
            fifth_moment.reshape(H, W)
        ], dim=0)
        
        return HOS_matrix
    
    def DMD(self,data, truncation=20):
        """
        Dynamic Mode Decomposition (DMD) for thermographic sequences.
        
        Args:
            data: 3D array (N_frames, H, W) - Thermal sequence.
            truncation: Rank for SVD truncation. If None, uses full rank.
            
        Returns:
            dmd_modes: Shape (truncation, H, W) - DMD modes (spatial patterns).
            eig_vals: Eigenvalues of the reduced operator.
        """
        # Reshape and transpose to (H*W, N_frames)
        dmd_ready = data.reshape(data.shape[0], -1).T  # (H*W, N)
        
        # Normalize (MinMax scales each pixel across time)
        dmd_ready = MinMaxScaler().fit_transform(dmd_ready)
        
        # Create time-shifted matrices X (t) and X' (t+1)
        X = dmd_ready[:, :-1]  # (H*W, N-1)
        X_p = dmd_ready[:, 1:]  # (H*W, N-1)
        
        # Truncated SVD of X
        U, s, Vh = svd(X, full_matrices=False)
        if truncation is not None:
            U = U[:, :truncation]
            s = s[:truncation]
            Vh = Vh[:truncation, :]
        
        # Build reduced operator A_tilde
        Sigma_inv = np.diag(1.0 / s)
        A_tilde = U.T @ X_p @ Vh.T @ Sigma_inv  # (truncation, truncation)
        
        # Eigen decomposition of A_tilde
        eig_vals, eig_vecs = eig(A_tilde)
        
        # Reconstruct DMD modes (project back to full space)
        DMD_modes = X_p @ Vh.T @ Sigma_inv @ eig_vecs  # (H*W, truncation)
        DMD_modes = DMD_modes.T.reshape(-1, data.shape[1], data.shape[2])  # (truncation, H, W)
        
        return DMD_modes, eig_vals


    def DMD_torch(self, data, truncation=20):
        """
        Dynamic Mode Decomposition (DMD) for thermographic sequences (PyTorch version).
        
        Args:
            data: 3D tensor (N_frames, H, W) - Thermal sequence.
            truncation: Rank for SVD truncation. If None, uses full rank.
            
        Returns:
            dmd_modes: Shape (truncation, H, W) - DMD modes (spatial patterns).
            eig_vals: Eigenvalues of the reduced operator.
        """
        # Input validation and device handling
        if not isinstance(data, torch.Tensor):
            data = torch.tensor(data, dtype=torch.float32)
        device = data.device
        
        N, H, W = data.shape
        
        # Reshape and normalize (min-max scaling with epsilon)
        dmd_ready = data.reshape(N, -1).T  # (H*W, N)
        min_vals = dmd_ready.min(dim=1, keepdim=True)[0]
        max_vals = dmd_ready.max(dim=1, keepdim=True)[0]
        dmd_ready = (dmd_ready - min_vals) / (max_vals - min_vals + 1e-10)
        
        # Time-shifted matrices
        X = dmd_ready[:, :-1]  # (H*W, N-1)
        X_p = dmd_ready[:, 1:]  # (H*W, N-1)
        
        # Truncated SVD
        U, s, Vh = torch.linalg.svd(X, full_matrices=False)
        if truncation is not None:
            truncation = min(truncation, s.shape[0])  # Safety check
            U = U[:, :truncation]
            s = s[:truncation]
            Vh = Vh[:truncation, :]
        
        # Build reduced operator (A_tilde)
        Sigma_inv = torch.diag(1.0 / (s + 1e-10)).to(device)  # Regularized inverse
        A_tilde = U.T @ X_p @ Vh.T @ Sigma_inv  # (truncation, truncation)
        
        # Eigen decomposition (returns complex values)
        eig_vals, eig_vecs = torch.linalg.eig(A_tilde)
        
        # Convert all components to complex64 for reconstruction
        X_p = X_p.to(torch.complex64)
        Vh = Vh.to(torch.complex64)
        Sigma_inv = Sigma_inv.to(torch.complex64)
        
        # Reconstruct DMD modes (all operations now in complex64)
        DMD_modes = X_p @ Vh.T @ Sigma_inv @ eig_vecs  # (H*W, truncation)
        DMD_modes = DMD_modes.T.reshape(-1, H, W)  # (truncation, H, W)
        
        return DMD_modes, eig_vals

    #--------------------------------------------------------------------------------Filtering methods-----------------------------------------------------------------------------

    def SavGol(self,data, window_length, polyorder, axis=0):
        """
        Vectorized Savitzky-Golay filtering for thermographic sequences.
        
        Args:
            data: 3D array (N_frames, H, W) - Thermal sequence.
            window_length: Length of the filter window (must be odd).
            polyorder: Order of the polynomial fit.
            axis: Axis to filter along (default=0, time dimension).
            
        Returns:
            Filtered data with same shape as input.
        """
        # Input validation
        if window_length % 2 != 1:
            raise ValueError("window_length must be odd")
        if polyorder >= window_length:
            raise ValueError("polyorder must be less than window_length")

        # Vectorized filtering
        return savgol_filter(data, window_length, polyorder, axis=axis)

    def binarize_mask(self, frame, threshold_value=0.5):
        """
        Creates a binary mask from a thermography frame (supports both NumPy and PyTorch).
        
        Args:
            frame: Single thermogram (2D NumPy array or PyTorch tensor)
            threshold_value: Threshold value in range [0,1] after normalization
            
        Returns:
            Binary mask (same type as input) where:
                - 1 = pixels ≥ threshold
                - 0 = pixels < threshold
                
        Raises:
            ValueError: If input is not 2D or threshold is outside [0,1]
            RuntimeError: If frame contains NaN/inf values
        """
        # Determine input type and setup operations
        is_torch = hasattr(frame, 'cuda')  # Check if PyTorch tensor
        lib = torch if is_torch else np
        
        # Input validation
        if frame.ndim != 2:
            raise ValueError("Input must be 2D array/tensor")
            
        if not 0 <= threshold_value <= 1:
            raise ValueError(f"Threshold must be in [0,1], got {threshold_value}")
            
        if lib.isnan(frame).any() or lib.isinf(frame).any():
            raise RuntimeError("Input contains NaN/inf values")
        
        # Normalize to [0,1] range
        frame_min = frame.min()
        frame_range = frame.max() - frame_min
        if frame_range == 0:  # Handle uniform frames
            return lib.zeros_like(frame)
        
        norm_frame = (frame - frame_min) / frame_range
        
        # Create binary mask
        if is_torch:
            binary_mask = (norm_frame >= threshold_value).type(frame.dtype)
            if frame.is_cuda:  # Preserve GPU placement
                binary_mask = binary_mask.to(frame.device)
        else:
            binary_mask = np.where(norm_frame >= threshold_value, 1, 0).astype(np.uint8)
        
        return binary_mask
    
    def svd_denoise_2d(self,image, rank=10):
        """
        Denoise a 2D image via low-rank SVD approximation.
        
        Args:
            image (torch.Tensor): Input 2D image (H, W).
            rank (int): Rank for truncation. Must be <= min(H, W).
        
        Returns:
            denoised_image (torch.Tensor): Rank-'rank' approximation of input.
            S (torch.Tensor): Singular values (for analysis).
        """
        assert rank <= min(image.shape), f"Rank must be <= {min(image.shape)}"
        
        # Compute SVD
        U, S, Vh = torch.linalg.svd(image, full_matrices=False)
        
        # Truncate to rank-k
        Uk, Sk, Vhk = U[:, :rank], S[:rank], Vh[:rank, :]
        
        # Reconstruct denoised image
        denoised_image = Uk @ torch.diag(Sk) @ Vhk
        
        return denoised_image, S
    
    def svd_denoise(self,video_frames, rank=10):
        """
        Denoise a 3D Tensor via low-rank SVD approximation.
        
        Args:
            video_frames (torch.Tensor): Input 3D tensor (T, H, W).
            rank (int): Rank for truncation. Must be <= min(H, W).
        
        Returns:
            denoised_tensor (torch.Tensor): Rank-'rank' approximation of input.
            S (torch.Tensor): Singular values (for analysis).
        """
        
        T, H, W = video_frames.shape
        X = video_frames.view(T, -1)
        
        U, S, Vh = torch.linalg.svd(X, full_matrices=False)
        
        rank = min(rank, S.shape[0])
        Uk, Sk, Vhk = U[:, :rank], S[:rank], Vh[:rank, :]
        
        X_denoised = (Uk * Sk) @ Vhk

        return X_denoised.view(T, H, W),S
    
    def MeanFil(self, data, window_size=5, axis=0):
        """
        Sliding window mean filter for 3D thermography data.
        
        Args:
            data: Input array (N_frames, H, W)
            window_size: Size of the averaging window (odd integer)
            axis: Axis to filter along (default=0 for temporal filtering)
            
        Returns:
            Filtered array with same shape as input
        """
        if window_size % 2 == 0:
            raise ValueError("Window size must be odd")
        
        pad_width = [(0,0)] * data.ndim
        pad_width[axis] = (window_size//2, window_size//2)
        
        # Reflective padding to handle edges
        padded = np.pad(data, pad_width, mode='reflect')
        
        # Create sliding window view
        strides = padded.strides + (padded.strides[axis],)
        shape = padded.shape[:axis] + (padded.shape[axis] - window_size + 1,) + padded.shape[axis+1:] + (window_size,)
        windows = np.lib.stride_tricks.as_strided(
            padded,
            shape=shape,
            strides=strides
        )
        
        return np.mean(windows, axis=-1)
    
    def robust_normalize_global(self,data):
        """
        Normalization of global thermogram sequence.
        
        Args:
            data: Input array (N_frames, H, W)
            
        Returns:
            Normalized array with same shape as input
        """

        max=data.max()
        min=data.min()

        return (data-min)/(max-min+1e-8) #To avoid division by zero
    
    def robust_standardize_global(self,data):
        """
        Standardization of global thermogram sequence.
        
        Args:
            data: Input array (N_frames, H, W)
            
        Returns:
            Standardized array with same shape as input
        """
        mean = data.mean()
        std = data.std()
        
        return (data - mean) / (std+1e-8) #To avoid division by zero
    

    def dmd_background_removal(video_frames, rank=10, device='cpu'):
        """
        Args:
            video_frames (torch.Tensor): Complex tensor of shape (T, H, W) or (T, C, H, W)
            rank (int): Rank for low-rank approximation
            device (str): 'cuda' or 'cpu'
        Returns:
            background (torch.Tensor): Background video (T, H, W)
            foreground (torch.Tensor): Foreground video (T, H, W)
        """
        # Convert to grayscale if RGB and ensure complex dtype
        if video_frames.dim() == 4:
            video_frames = video_frames.mean(dim=1)  # Convert RGB to grayscale
        if not video_frames.is_complex():
            video_frames = video_frames.to(torch.complex64)
        video_frames = video_frames.to(device)
        
        T, H, W = video_frames.shape
        X = video_frames.view(T, -1).T  # Reshape to (H*W, T)

        # Split into time-shifted matrices
        X1 = X[:, :-1]
        X2 = X[:, 1:]

        # Step 1: SVD with complex support
        U, S, Vh = torch.linalg.svd(X1, full_matrices=False)
        U, S, Vh = U[:, :rank], S[:rank], Vh[:rank, :]  # Truncate to rank
        
        # Step 2: Low-rank dynamics matrix (ensure complex operations)
        Sinv = torch.diag(1.0 / S).to(torch.complex64)
        A_tilde = U.T.conj() @ X2 @ Vh.T.conj() @ Sinv  # Proper complex matrix mult
        
        # Step 3: Eigendecomposition
        eigvals, eigvecs = torch.linalg.eig(A_tilde)
        
        # Step 4: DMD modes
        Phi = X2 @ Vh.T.conj() @ Sinv @ eigvecs
        
        # Step 5: Select background modes (|λ| ≈ 1)
        bg_mask = torch.abs(eigvals - 1.0) < 0.05
        Phi_bg = Phi[:, bg_mask]
        eigvals_bg = eigvals[bg_mask]
        
        # Step 6: Reconstruct background (complex-aware)
        b = torch.linalg.lstsq(Phi_bg, X1[:, 0]).solution
        Vandermonde = torch.vander(eigvals_bg, T-1, increasing=True).to(torch.complex64)
        X_bg = Phi_bg @ (b.unsqueeze(1) * Vandermonde)
        
        # Reshape and pad
        background = torch.zeros_like(X, dtype=torch.complex64)
        background[:, :-1] = X_bg
        background = background.T.view(T, H, W)
        
        # Foreground (complex subtraction)
        foreground = video_frames - background
        
        return background.real, foreground.real  # Return real parts if needed