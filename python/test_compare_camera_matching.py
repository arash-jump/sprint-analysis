import unittest
from unittest.mock import Mock
import cv2
import numpy as np
from compare_camera_matching import orb_correspondences, ratio_matches
from diagnose_camera_motion import estimate_link, project


class CompareCameraMatchingTest(unittest.TestCase):
    def test_ratio_and_mutual_remove_ambiguous_and_duplicate_pairs(self):
        def m(q,t,d): return cv2.DMatch(q,t,float(d))
        forward=[[m(0,0,1),m(0,1,10)],[m(1,1,9),m(1,0,10)],[m(2,0,2),m(2,1,10)]]
        reverse=[[m(0,0,1),m(0,1,10)],[m(1,1,1),m(1,0,10)]]
        result,nf,nr=ratio_matches(forward,reverse)
        self.assertEqual((nf,nr),(2,2))
        self.assertEqual([(x.queryIdx,x.trainIdx) for x in result],[(0,0)])

    def test_orb_recovers_known_translation_and_masks_are_respected(self):
        rng=np.random.default_rng(42)
        source=rng.integers(0,256,(400,600),dtype=np.uint8)
        target=cv2.warpAffine(source,np.float32([[1,0,12],[0,1,8]]),(600,400))
        mask=np.full_like(source,255);mask[150:250,200:350]=0
        old,new,counts=orb_correspondences(source,target,mask,mask)
        self.assertGreater(counts['mutual_unique'],30)
        self.assertTrue(all(mask[int(y),int(x)] for x,y in old))
        self.assertTrue(all(mask[int(y),int(x)] for x,y in new))
        matrix,info,_,_=estimate_link(old,new,600,400)
        self.assertTrue(info['valid'],info)
        np.testing.assert_allclose(project(matrix,[[100,100]]),[[112,108]],atol=1.5)

    def test_no_features_and_false_matches_fail_closed(self):
        source=np.zeros((200,300),np.uint8); mask=np.full_like(source,255)
        old,new,_=orb_correspondences(source,source,mask,mask)
        self.assertEqual(len(old),0)
        self.assertEqual(estimate_link(old,new,300,200)[1]['reason'],'insufficient_correspondences')
        rng=np.random.default_rng(7); old=rng.uniform([0,0],[300,200],(50,2));new=rng.uniform([0,0],[300,200],(50,2))
        matrix,info,_,_=estimate_link(old,new,300,200)
        self.assertIsNone(matrix)
        self.assertFalse(info['valid'])

if __name__=='__main__': unittest.main()
