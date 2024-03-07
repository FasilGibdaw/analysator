from scipy.spatial import Delaunay
import numpy as np
from scipy.interpolate import LinearNDInterpolator
from operator import itemgetter
# from time import time
import warnings

importerror = None

try:
   from scipy.interpolate import RBFInterpolator
except Exception as e:
   importerror = e
   class RBFInterpolator(object):
      def __init__(self, pts, vals, **kwargs):
         raise importerror #Exception("Module load error")
   


# With values fi at hexahedral vertices and trilinear basis coordinates ksi,
# return the trilinear interpolant for fi
# Vectorized. Assumes that the first dimension ksii, fii are the index for an individual query - 
# singleton dimension required for a single query!
def f(ksii, fii):
   ksi = np.atleast_2d(ksii)
   if(fii.ndim == 1):
      fi = fii[np.newaxis,:,np.newaxis]
   elif(fii.ndim == 2):
      fi = fii
      res = (1-ksi[:,0]) * (1-ksi[:,1]) * (1-ksi[:,2]) * fi[:,0] + \
               ksi[:,0]  * (1-ksi[:,1]) * (1-ksi[:,2]) * fi[:,1] + \
            (1-ksi[:,0]) *    ksi[:,1]  * (1-ksi[:,2]) * fi[:,2] + \
               ksi[:,0]  *    ksi[:,1]  * (1-ksi[:,2]) * fi[:,3] + \
            (1-ksi[:,0]) * (1-ksi[:,1]) *    ksi[:,2]  * fi[:,4] + \
               ksi[:,0]  * (1-ksi[:,1]) *    ksi[:,2]  * fi[:,5] + \
            (1-ksi[:,0]) *    ksi[:,1]  *    ksi[:,2]  * fi[:,6] + \
               ksi[:,0]  *    ksi[:,1]  *    ksi[:,2]  * fi[:,7]
      return res
   else:
      fi = fii

   # this broadcasts to ksi@ksi shape for scalar fis for whatever reason, so above
   res = (1-ksi[:,0,None]) * (1-ksi[:,1,None]) * (1-ksi[:,2,None]) * fi[:,0,:] + \
            ksi[:,0,None]  * (1-ksi[:,1,None]) * (1-ksi[:,2,None]) * fi[:,1,:] + \
         (1-ksi[:,0,None]) *    ksi[:,1,None]  * (1-ksi[:,2,None]) * fi[:,2,:] + \
            ksi[:,0,None]  *    ksi[:,1,None]  * (1-ksi[:,2,None]) * fi[:,3,:] + \
         (1-ksi[:,0,None]) * (1-ksi[:,1,None]) *    ksi[:,2,None]  * fi[:,4,:] + \
            ksi[:,0,None]  * (1-ksi[:,1,None]) *    ksi[:,2,None]  * fi[:,5,:] + \
         (1-ksi[:,0,None]) *    ksi[:,1,None]  *    ksi[:,2,None]  * fi[:,6,:] + \
            ksi[:,0,None]  *    ksi[:,1,None]  *    ksi[:,2,None]  * fi[:,7,:]
   if(res.shape[-1] == 1):
      return np.squeeze(res, axis = -1)
   else:
      return res


# With values fi at hexahedral vertices and trilinear basis coordinates ksi,
# return the interpolated gradient/jacobian of fi wrt. the trilinear basis at ksi
# Vectorized. Assumes that the first dimension ksii, fii are the index for an individual query - 
# singleton dimension required for a single query!
# does not handle scalars?
def df(ksii, fii):
   ksi = np.atleast_2d(ksii)
   # print(fii.shape)
   if(fii.ndim == 1):
      fi = fii[np.newaxis,:,np.newaxis]
   elif(fii.ndim == 2):
      fi = np.atleast_3d(fii)#fii[:,:,np.newaxis]
   else:
      fi = fii
   # print(fi)
   # print(fi.shape)
   d0 =  -1 * (1-ksi[:,1,None]) * (1-ksi[:,2,None]) * fi[:,0,:] + \
          1 * (1-ksi[:,1,None]) * (1-ksi[:,2,None]) * fi[:,1,:] + \
         -1 *    ksi[:,1,None]  * (1-ksi[:,2,None]) * fi[:,2,:] + \
          1 *    ksi[:,1,None]  * (1-ksi[:,2,None]) * fi[:,3,:] + \
         -1 * (1-ksi[:,1,None]) *    ksi[:,2,None]  * fi[:,4,:] + \
          1 * (1-ksi[:,1,None]) *    ksi[:,2,None]  * fi[:,5,:] + \
         -1 *    ksi[:,1,None]  *    ksi[:,2,None]  * fi[:,6,:] + \
          1 *    ksi[:,1,None]  *    ksi[:,2,None]  * fi[:,7,:]
   d1 =  (1-ksi[:,0,None]) * -1  * (1-ksi[:,2,None]) * fi[:,0,:] + \
            ksi[:,0,None]  * -1  * (1-ksi[:,2,None]) * fi[:,1,:] + \
         (1-ksi[:,0,None]) *  1  * (1-ksi[:,2,None]) * fi[:,2,:] + \
            ksi[:,0,None]  *  1  * (1-ksi[:,2,None]) * fi[:,3,:] + \
         (1-ksi[:,0,None]) * -1  *    ksi[:,2,None]  * fi[:,4,:] + \
            ksi[:,0,None]  * -1  *    ksi[:,2,None]  * fi[:,5,:] + \
         (1-ksi[:,0,None]) *  1  *    ksi[:,2,None]  * fi[:,6,:] + \
            ksi[:,0,None]  *  1  *    ksi[:,2,None]  * fi[:,7,:]
   d2 =  (1-ksi[:,0,None]) * (1-ksi[:,1,None]) * -1 * fi[:,0,:] + \
            ksi[:,0,None]  * (1-ksi[:,1,None]) * -1 * fi[:,1,:] + \
         (1-ksi[:,0,None]) *    ksi[:,1,None]  * -1 * fi[:,2,:] + \
            ksi[:,0,None]  *    ksi[:,1,None]  * -1 * fi[:,3,:] + \
         (1-ksi[:,0,None]) * (1-ksi[:,1,None]) *  1 * fi[:,4,:] + \
            ksi[:,0,None]  * (1-ksi[:,1,None]) *  1 * fi[:,5,:] + \
         (1-ksi[:,0,None]) *    ksi[:,1,None]  *  1 * fi[:,6,:] + \
            ksi[:,0,None]  *    ksi[:,1,None]  *  1 * fi[:,7,:]
   res = np.stack((d0,d1,d2),axis = -1)
   return res

# For hexahedral vertices verts and point p, find the trilinear basis coordinates ksi
# that interpolate the coordinates of verts to the tolerance tol.
# This is an iterative procedure. Return nans in case of no convergence.
def find_ksi(p, v_coords, tol= 1e-7, maxiters = 200):
   p = np.atleast_2d(p)
   v_coords = np.atleast_3d(v_coords)
   ksi0 = np.full_like(p, 0.5)
   J = df(ksi0, v_coords)
   # print("J", J)
   ksi_n = ksi0
   ksi_n1 = np.full_like(ksi0, np.nan)
   f_n =  f(ksi_n,v_coords)
   # print(f_n.shape, p.shape)
   # print(f_n)
   f_n = f_n - p

   convergence = np.full((p.shape[0],),False, dtype=bool)
   for i in range(maxiters):
      
      J[~convergence,:,:] = df(ksi_n[~convergence,:], v_coords[~convergence,:,:])
      # print('J',J[~convergence,...])
      f_n[~convergence,:] = f(ksi_n[~convergence,:],v_coords[~convergence,:,:])-p[~convergence,:]
      # print('fn',f_n[~convergence,...])
      # print("f(r) = ", f_n)
      # step = np.matmul(np.linalg.inv(J),f_n)
      # print(J.shape, f_n.shape)
      step = np.linalg.solve(J[~convergence,:,:], -f_n[~convergence,:])
      # print("J^-1 f0 = ",step)
      ksi_n1[~convergence,:] = step + ksi_n[~convergence,:] # r_(n+1) 
      ksi_n[~convergence,:] = ksi_n1[~convergence,:]
      
      # print(ksi_n1, f(ksi_n1,verts), np.linalg.norm(f(ksi_n1,verts) - p))
      # print("--------------")
      convergence[~convergence] = (np.linalg.norm(f(ksi_n1[~convergence,:],v_coords[~convergence,:,:]) - p[~convergence,:],axis=1) < tol)
         # convergence = True
      if np.all(convergence):
         # print("All converged in ", i, "iterations")
         return ksi_n1
      

   if np.all(convergence):
      # print("Converged after ", i, "iterations")
      return ksi_n1
   else:
      # warnings.warn("Generalized trilinear interpolation did not converge for " + str(np.sum(~convergence)) + " points. Nans inbound.")
      ksi_n1[~convergence,:] = np.nan
      return ksi_n1
      
class HexahedralTrilinearInterpolator(object):
   ''' Class for doing general hexahedral interpolation, including degenerate hexahedra (...eventually).
   '''

   def __init__(self, pts, vals, **kwargs):
      self.pts = pts
      self.vals = vals
      # Call dual construction from here?
      self.reader = kwargs['reader']
      self.var = kwargs['var']
      self.operator = kwargs['op']

   def __call__(self, pt):
      pts = np.atleast_2d(pt)
      if(len(pts.shape) == 2):
         # t0 = time()
         vals = []
         duals = []
         ksis = []
         # for i,p in enumerate(pt):
         #    d, ksi = self.reader.get_dual(p)
         #    duals.append(d)
         #    ksis.append(ksi)
         duals, ksis = self.reader.get_dual(pts)
         duals_corners = np.array(itemgetter(*duals)(self.reader._VlsvReader__dual_cells))
         fi = self.reader.read_variable(self.var, duals_corners.reshape(-1), operator=self.operator)
         if(fi.ndim == 2):
            val_len = fi.shape[1]
         else:
            val_len = 1
         ksis = np.array(ksis).squeeze() # n x 1 x 3 ...... fix
         # print(ksis.shape, fi.shape)
         if(val_len == 1):
            fi = fi.reshape((-1,8))
         else:
            fi = fi.reshape((-1,8,val_len))
         # print('fi reshaped', fi.shape)
         vals = f(ksis, fi)
         # print("irregular interpolator __call__ done in", time()-t0,"s")
         return vals
      
         # the following loop is not reached, kept for reference
         for i,p in enumerate(pts):
            # dual, ksi = self.reader.get_dual(np.atleast_2d(p))
            # dual = dual[0]
            # ksi = ksi[0]
            # print("regular:",i,dual, ksi)
            dual = duals[i]
            ksi = ksis[i]
            # print("from batch:", dual, ksi)
            if dual is None:
               vals.append(np.nan)
            else:
               # dual_corners = self.reader._VlsvReader__dual_cells[dual]
               dual_corners = duals_corners[i]
               fp = f(ksi, self.reader.read_variable(self.var, np.array(dual_corners), operator=self.operator)[np.newaxis,:])
               vals.append(fp)
         return np.array(vals)
      else:
         dual, ksi = self.reader.get_dual(pt)
         dual_corners = self.__dual_cells[dual]
         fp = f(ksi, self.reader.read_variable(self.var, np.array(dual_corners), operator=self.operator)[np.newaxis,:])
         return fp


class AMRInterpolator(object):
   ''' Wrapper class for interpolators, esp. at refinement interfaces.
   Supported methods:
   Trilinear
      - (nearly) C0 continuous, regular-grid trilinear interpolant extended to collapsed hexahedral cells.
      - Non-parametric
      - Exact handling of multiply-degenerate hexahedra is missing, with the enabling hack causing errors in trilinear coordinate on the order of 1m


   Radial Basis Functions, RBF
      - Accurate, slow-ish, but hard to make properly continuous and number of neighbors on which to base the interpolant is not trivial to find.
      - Not continuous with regular-grid trilinear interpolants, needs to be used in the entire interpolation domain.
      - kword options: "neighbors" for number of neighbors (64)
      - basis function uses SciPy default. A free parameter.

   Delaunay (not recommended)
      - Choice of triangulation is not unique with regular grids, including refinement interfaces.
      - kword options as in qhull; "qhull_options" : "QJ" (breaks degeneracies)

   '''

   def __init__(self, reader, method = "Trilinear", cellids=np.array([1,2,3,4,5],dtype=np.int64)):
      self.__reader = reader
      self.__cellids = np.array(list(set(cellids)),dtype=np.int64)
      self.duals = {}
      # Cannot initialize an empty Delaunay
      #self.__Delaunay = Delaunay(reader.get_cell_coordinates(self.__cellids), incremental = True, qhull_options="QJ Qc Q12")

   def add_cells(self, cells):
      new_cells = [c for c in cells if c not in self.__cellids]
      self.__cellids = np.append(self.__cellids, new_cells)
      
   def get_points(self):
      return self.__reader.get_cell_coordinates(self.__cellids)
   
   def get_interpolator(self, name, operator, coords, 
                        method="Trilinear", 
                        methodargs={
                           "RBF":{"neighbors":64}, # Harrison-Stetson number of neighbors
                           "Delaunay":{"qhull_options":"QJ"}
                           }):
      methodargs["Trilinear"] = {"reader":self.__reader, "var" : name, "op":operator}

      pts = self.__reader.get_cell_coordinates(self.__cellids)
      vals = self.__reader.read_variable(name, self.__cellids, operator=operator)
      if method == "Delaunay":
         self.__Delaunay = Delaunay(self.reader.get_cell_coordinates(self.__cellids),**methodargs[method])
         return LinearNDInterpolator(self.__Delaunay, vals)
      elif method == "RBF":
         try:
            return RBFInterpolator(pts, vals, **methodargs[method])
         except Exception as e:
            warnings.warn("RBFInterpolator could not be imported. SciPy >= 1.7 is required for this class. Falling back to Hexahedral trilinear interpolator. Error given was " + str(e))
            return HexahedralTrilinearInterpolator(pts, vals, **methodargs["Trilinear"])
      elif method == "Trilinear":
         return HexahedralTrilinearInterpolator(pts, vals, **methodargs[method])

